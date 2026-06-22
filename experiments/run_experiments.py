"""Budget Guru – Experiments runner.

Runs all combinations of prompt variants × model names against the full
Budget Guru dataset, applies evaluators, and prints a summary table.
Results are also forwarded to Datadog LLM Experiments via stub helpers
that can be filled in once the SDK is available.

Usage:
    python -m experiments.run_experiments \\
        --dataset ./datasets/budget_guru_investment_qa.csv \\
        --models model_A model_B \\
        --prompts P1 P2 P3 P4
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import os
import sys
from typing import Any

from experiments.datasets import DatasetRecord, create_or_get_dataset_in_datadog, load_budget_guru_dataset
from experiments.evaluators import EVALUATORS
from app.config import config
from app.llm_client import LLMClient
from app.prompts import get_system_prompt

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ExperimentConfig:
    """Describes a single experiment run (one model × one prompt variant)."""

    model_name: str
    prompt_variant: str


@dataclasses.dataclass
class EvalResult:
    """Evaluation outcome for a single dataset record in one experiment."""

    record_id: str
    model_name: str
    prompt_variant: str
    output: str
    scores: dict[str, float | bool]


# ---------------------------------------------------------------------------
# Datadog Experiments integration stubs
# ---------------------------------------------------------------------------


def log_experiment_result_to_datadog(
    dataset_id: str,
    experiment_config: ExperimentConfig,
    record: DatasetRecord,
    output: str,
    evals: dict[str, Any],
) -> None:
    """Send a single evaluation result to Datadog LLM Experiments.

    This is a *stub*.  Replace the body with the real SDK call once available.

    Expected Datadog API interaction:
        POST /api/v2/llm-obs/experiments/{experiment_id}/events
        Body: {
            "data": {
                "type": "experiment_events",
                "attributes": {
                    "dataset_id": dataset_id,
                    "input": record.input,
                    "output": output,
                    "expected_output": record.expected_output,
                    "evaluations": evals,
                    "tags": {
                        "model": experiment_config.model_name,
                        "prompt_variant": experiment_config.prompt_variant,
                        "topic": record.topic,
                        "difficulty": record.difficulty,
                    }
                }
            }
        }

    Reference: https://docs.datadoghq.com/llm_observability/experiments/

    Args:
        dataset_id: The Datadog dataset ID returned by create_or_get_dataset_in_datadog().
        experiment_config: Model and prompt metadata for this run.
        record: The dataset row being evaluated.
        output: The LLM-generated answer.
        evals: Dict of evaluator name → score.
    """
    # [Datadog LLM Experiments SDK] Replace stub below:
    #   from ddtrace.llmobs.experiments import Experiment
    #   experiment = Experiment.get_or_create(
    #       name=f"{experiment_config.model_name}-{experiment_config.prompt_variant}",
    #       dataset_id=dataset_id,
    #       ml_app=config.DD_LLMOBS_ML_APP,
    #   )
    #   experiment.log(
    #       input=record.input,
    #       output=output,
    #       expected_output=record.expected_output,
    #       evaluations=evals,
    #       tags={...},
    #   )
    logger.debug(
        "[stub] log_experiment_result_to_datadog: dataset_id=%s record_id=%s evals=%s",
        dataset_id,
        record.id,
        evals,
    )


# ---------------------------------------------------------------------------
# Core experiment logic
# ---------------------------------------------------------------------------


def run_single_experiment(
    experiment_config: ExperimentConfig,
    records: list[DatasetRecord],
    llm_client: LLMClient,
    dataset_id: str,
) -> list[EvalResult]:
    """Run one model × prompt combination over all dataset records.

    For each record:
    1. Generate an answer with the LLM.
    2. Apply all evaluators.
    3. Forward results to Datadog (stub).

    Args:
        experiment_config: Model name and prompt variant for this run.
        records: All dataset rows to evaluate.
        llm_client: Shared LLM client instance.
        dataset_id: Datadog dataset ID for logging.

    Returns:
        List of EvalResult, one per dataset record.
    """
    system_prompt = get_system_prompt(experiment_config.prompt_variant)
    results: list[EvalResult] = []

    for record in records:
        try:
            output = llm_client.generate(
                system_prompt=system_prompt,
                user_message=record.input,
                metadata={
                    "experiment": True,
                    "model": experiment_config.model_name,
                    "prompt_variant": experiment_config.prompt_variant,
                    "record_id": record.id,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "LLM call failed for record %s: %s", record.id, exc
            )
            output = ""

        scores: dict[str, float | bool] = {}
        for name, fn in EVALUATORS.items():
            try:
                scores[name] = fn(
                    output=output,
                    expected_output=record.expected_output,
                    llm_client=llm_client,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Evaluator %s failed for record %s: %s", name, record.id, exc)
                scores[name] = 0.0

        log_experiment_result_to_datadog(
            dataset_id=dataset_id,
            experiment_config=experiment_config,
            record=record,
            output=output,
            evals=scores,
        )

        results.append(
            EvalResult(
                record_id=record.id,
                model_name=experiment_config.model_name,
                prompt_variant=experiment_config.prompt_variant,
                output=output,
                scores=scores,
            )
        )
        logger.info(
            "  record=%s scores=%s",
            record.id,
            {k: round(float(v), 3) for k, v in scores.items()},
        )

    return results


def aggregate_scores(results: list[EvalResult]) -> dict[str, float]:
    """Compute the mean score for each evaluator across all results.

    Args:
        results: Flat list of EvalResult instances for one experiment.

    Returns:
        Dict mapping evaluator name → mean score.
    """
    if not results:
        return {}
    totals: dict[str, float] = {k: 0.0 for k in results[0].scores}
    for r in results:
        for k, v in r.scores.items():
            totals[k] += float(v)
    n = len(results)
    return {k: round(v / n, 4) for k, v in totals.items()}


def print_summary(all_results: dict[str, list[EvalResult]]) -> None:
    """Print a formatted summary table of mean scores per experiment.

    Args:
        all_results: Mapping of ``"<model>/<prompt>"`` → list of EvalResult.
    """
    if not all_results:
        print("No results to display.")
        return

    eval_keys = list(next(iter(all_results.values()))[0].scores.keys())
    col_w = 14
    header = f"{'Experiment':<30}" + "".join(f"{k:>{col_w}}" for k in eval_keys)
    print("\n" + "=" * len(header))
    print("Budget Guru – Experiments Summary")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for label, results in sorted(all_results.items()):
        means = aggregate_scores(results)
        row = f"{label:<30}" + "".join(f"{means.get(k, 0.0):>{col_w}.4f}" for k in eval_keys)
        print(row)

    print("=" * len(header) + "\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Run Budget Guru LLM Experiments offline."
    )
    parser.add_argument(
        "--dataset",
        default="./datasets/budget_guru_investment_qa.csv",
        help="Path to the Q&A CSV dataset.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["model_A"],
        help="Model name(s) to evaluate (e.g. model_A model_B).",
    )
    parser.add_argument(
        "--prompts",
        nargs="+",
        default=["P1", "P4"],
        help="Prompt variant(s) to evaluate (P1–P4).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point for the Experiments runner."""
    args = parse_args(argv)

    # Load dataset
    records = load_budget_guru_dataset(args.dataset)
    logger.info("Dataset loaded: %d records", len(records))

    # Register dataset in Datadog (stub)
    dataset_id = create_or_get_dataset_in_datadog(records)
    logger.info("Datadog dataset_id: %s", dataset_id)

    all_results: dict[str, list[EvalResult]] = {}

    for model_name in args.models:
        # Build an LLM client per model (base_url and api_key from env)
        llm_client = LLMClient(
            model_name=model_name,
            api_key=config.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", ""),
            base_url=config.OPENAI_BASE_URL,
            timeout=config.LLM_TIMEOUT,
        )

        for prompt_variant in args.prompts:
            exp_cfg = ExperimentConfig(
                model_name=model_name,
                prompt_variant=prompt_variant,
            )
            label = f"{model_name}/{prompt_variant}"
            logger.info("Running experiment: %s (%d records)", label, len(records))

            results = run_single_experiment(
                experiment_config=exp_cfg,
                records=records,
                llm_client=llm_client,
                dataset_id=dataset_id,
            )
            all_results[label] = results

    print_summary(all_results)


if __name__ == "__main__":
    main(sys.argv[1:])
