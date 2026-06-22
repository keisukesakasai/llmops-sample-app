"""Budget Guru – Experiments runner.

Runs all combinations of prompt variants × model names against the full
Budget Guru dataset using Datadog LLM Experiments SDK.

Usage:
    python -m experiments.run_experiments \\
        --dataset ./datasets/budget_guru_investment_qa.csv \\
        --models gpt-4.5 \\
        --prompts P1 P2 P3 P4
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any, Dict, Optional

from dotenv import load_dotenv
load_dotenv()

from app.config import config
from app.llm_client import LLMClient
from app.prompts import get_system_prompt
from app.datadog_instrumentation import init_tracer

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Datadog LLM Obs の初期化（Experiments でもトレースを残す）
init_tracer()


# ---------------------------------------------------------------------------
# Evaluators
# ---------------------------------------------------------------------------

def _extract_str(value: Any) -> str:
    """SDK が dict で渡してくる場合に文字列を取り出すヘルパー。"""
    if isinstance(value, dict):
        # {"expected_output": "..."} or {"output": "..."} の形式に対応
        return str(next(iter(value.values()), ""))
    return str(value or "")


def contains_keywords_eval(
    input_data: Dict[str, Any],
    output_data: Any,
    expected_output: Any,
) -> float:
    """重要キーワードの網羅率を 0〜1 で返す deterministic evaluator。"""
    import re
    expected = _extract_str(expected_output)
    output = _extract_str(output_data)
    STOP_WORDS = {
        "that", "this", "with", "from", "they", "have", "more", "than",
        "your", "also", "when", "some", "what", "just", "into", "over",
    }
    # 日本語対応：4文字以上のひらがな・カタカナ・漢字も対象にする
    keywords = set(
        w for w in re.findall(r"\b[a-z]{4,}\b|[぀-鿿]{2,}", expected.lower())
        if w not in STOP_WORDS
    )
    if not keywords:
        return 1.0
    output_lower = output.lower()
    matched = sum(1 for kw in keywords if kw in output_lower)
    return round(matched / len(keywords), 4)


def make_llm_accuracy_eval(llm_client: LLMClient):
    """information_accuracy の LLM-as-a-judge evaluator を返すファクトリ。"""
    def information_accuracy(
        input_data: Dict[str, Any],
        output_data: Any,
        expected_output: Any,
    ) -> float:
        expected = _extract_str(expected_output)
        output = _extract_str(output_data)
        judge_prompt = (
            f"模範回答: {expected}\n"
            f"モデルの回答: {output}\n"
            "モデルの回答が模範回答の内容をどれだけ正確かつ網羅的にカバーしているかを"
            "0.0〜1.0のスコアで評価してください。数字のみを返してください。"
        )
        try:
            raw = llm_client.generate(
                system_prompt="あなたは厳格で公平な評価者です。",
                user_message=judge_prompt,
            )
            return max(0.0, min(1.0, float(raw.strip())))
        except Exception as e:
            logger.warning("information_accuracy judge failed: %s", e)
            return 0.0
    return information_accuracy


def make_brand_voice_eval(llm_client: LLMClient):
    """brand_voice_consistency の LLM-as-a-judge evaluator を返すファクトリ。"""
    def brand_voice_consistency(
        input_data: Dict[str, Any],
        output_data: Any,
        expected_output: Any,
    ) -> bool:
        output = _extract_str(output_data)
        judge_prompt = (
            f"評価する回答:\n{output}\n\n"
            "この回答は、投資初心者の20代の若者に向けて、友達に話すような"
            "フレンドリーでわかりやすいスタイルで書かれていますか？"
            "「はい」または「いいえ」のみで答えてください。"
        )
        try:
            raw = llm_client.generate(
                system_prompt="あなたは若者向けフィンテックアプリのブランドボイス評価者です。",
                user_message=judge_prompt,
            ).strip()
            return raw.startswith("はい") or raw.lower().startswith("yes")
        except Exception as e:
            logger.warning("brand_voice_consistency judge failed: %s", e)
            return False
    return brand_voice_consistency


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Budget Guru LLM Experiments.")
    parser.add_argument(
        "--dataset",
        default="./datasets/budget_guru_investment_qa.csv",
        help="Path to the Q&A CSV dataset.",
    )
    parser.add_argument(
        "--models", nargs="+", default=["gpt-4.5"],
        help="Model name(s) to evaluate.",
    )
    parser.add_argument(
        "--prompts", nargs="+", default=["P1", "P4"],
        help="Prompt variant(s) to evaluate (P1–P4).",
    )
    parser.add_argument(
        "--project",
        default=config.DD_LLMOBS_PROJECT_NAME,
        help="Datadog Experiments project name.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point for the Experiments runner."""
    from ddtrace.llmobs import LLMObs

    args = parse_args(argv)

    # ------------------------------------------------------------------
    # 1. Dataset を Datadog に登録（or 既存を取得）
    # ------------------------------------------------------------------
    logger.info("Registering dataset: %s", args.dataset)
    dataset = LLMObs.create_dataset_from_csv(
        csv_path=args.dataset,
        dataset_name="budget-guru-investment-qa",
        project_name=args.project,
        description="Budget Guru investment Q&A evaluation dataset",
        input_data_columns=["input"],
        expected_output_columns=["expected_output"],
        metadata_columns=["topic", "difficulty", "age_group"],
    )
    logger.info("Dataset registered.")

    # ------------------------------------------------------------------
    # 2. model × prompt の組み合わせで Experiment を実行
    # ------------------------------------------------------------------
    for model_name in args.models:
        llm_client = LLMClient(
            model_name=model_name,
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
            timeout=config.LLM_TIMEOUT,
        )

        for prompt_variant in args.prompts:
            system_prompt = get_system_prompt(prompt_variant)
            experiment_name = f"budget-guru-{model_name}-{prompt_variant}"
            logger.info("Running experiment: %s", experiment_name)

            # タスク関数：1レコードの input を受け取り LLM の回答を返す
            # SDK の要件: 引数名は input_data と config でなければならない
            def task(
                input_data: Dict[str, Any],
                config: Optional[Dict[str, Any]] = None,
                _sp=system_prompt,
                _client=llm_client,
            ) -> str:
                return _client.generate(
                    system_prompt=_sp,
                    user_message=input_data["input"],
                    metadata={"prompt_variant": prompt_variant, "model": model_name},
                )

            # Evaluators
            evaluators = [
                contains_keywords_eval,
                make_llm_accuracy_eval(llm_client),
                make_brand_voice_eval(llm_client),
            ]

            # ------------------------------------------------------------------
            # Datadog LLM Experiments SDK で実行・送信
            # Reference: https://docs.datadoghq.com/llm_observability/experiments/setup/
            # ------------------------------------------------------------------
            experiment = LLMObs.experiment(
                name=experiment_name,
                task=task,
                dataset=dataset,
                evaluators=evaluators,
                description=f"Prompt variant {prompt_variant} with model {model_name}",
                config={"model": model_name, "prompt_variant": prompt_variant},
            )

            results = experiment.run()

            # 結果サマリーをコンソールに表示
            print(f"\n{'='*60}")
            print(f"Experiment: {experiment_name}")
            print(f"{'='*60}")
            for row in results.get("rows", []):
                print(f"  record={row.get('idx')} output={str(row.get('output',''))[:80]}")
            print(f"\nView in Datadog: {experiment.url}")

    print("\nAll experiments completed.")


if __name__ == "__main__":
    main(sys.argv[1:])
