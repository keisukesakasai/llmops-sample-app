"""Evaluators for Budget Guru LLM Experiments.

Two categories:
1. Deterministic (code-based) evaluators – no LLM calls needed.
2. LLM-as-a-judge evaluators – use the shared LLMClient (stubs for now).

All evaluators follow the same signature convention so the Experiments
runner can call them uniformly:

    score: float | bool = evaluator(output, expected_output, **kwargs)
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Deterministic evaluators
# ---------------------------------------------------------------------------


def exact_match(output: str, expected_output: str, **_: Any) -> bool:
    """Return True if ``output`` exactly matches ``expected_output``.

    Strips leading/trailing whitespace before comparison.
    Useful as a sanity-check for short, templated answers.
    """
    return output.strip() == expected_output.strip()


def contains_keywords(output: str, expected_output: str, **_: Any) -> float:
    """Score how many keywords from ``expected_output`` appear in ``output``.

    Extracts lowercase words ≥4 characters from ``expected_output`` as the
    keyword set, then measures recall in ``output``.

    Returns:
        A float in [0.0, 1.0] representing the fraction of keywords found.
    """
    keywords = set(
        w for w in re.findall(r"\b[a-z]{4,}\b", expected_output.lower())
        if w not in _STOP_WORDS
    )
    if not keywords:
        return 1.0  # nothing to check

    output_lower = output.lower()
    matched = sum(1 for kw in keywords if kw in output_lower)
    score = matched / len(keywords)
    logger.debug(
        "contains_keywords: matched=%d/%d score=%.3f", matched, len(keywords), score
    )
    return round(score, 4)


_STOP_WORDS: set[str] = {
    "that", "this", "with", "from", "they", "have", "more", "than",
    "your", "also", "when", "some", "what", "just", "into", "over",
    "even", "most", "each", "such", "very", "their", "there", "which",
    "about", "would", "could", "should", "often", "being", "been",
}


# ---------------------------------------------------------------------------
# 2. LLM-as-a-judge evaluators (stubs)
# ---------------------------------------------------------------------------


def information_accuracy(
    output: str,
    expected_output: str,
    llm_client: Any | None = None,
    **_: Any,
) -> float:
    """Score how completely ``output`` covers the information in ``expected_output``.

    Intended LLM prompt (to be implemented):
        System: "You are an expert evaluator."
        User: "Expected answer: {expected_output}\\nModel answer: {output}\\n
               Rate from 0 to 1 how accurately and completely the model answer
               covers the expected answer. Reply with only a number."

    Args:
        output: The model-generated answer.
        expected_output: The ground-truth answer from the dataset.
        llm_client: An instance of ``app.llm_client.LLMClient`` for the judge call.

    Returns:
        Float in [0.0, 1.0].  Returns 0.5 while stub is active.

    Datadog integration note:
        When calling via the Experiments SDK, wrap this function with
        ``@llmobs.annotate`` so the judge span is captured in the same trace.
    """
    if llm_client is None:
        logger.warning("information_accuracy: llm_client not provided, returning stub 0.5")
        return 0.5

    # [LLM-as-a-judge] Replace stub below with actual llm_client.generate() call
    # judge_prompt = (
    #     f"Expected answer: {expected_output}\n"
    #     f"Model answer: {output}\n"
    #     "Rate from 0.0 to 1.0 how accurately and completely the model answer "
    #     "covers the expected answer. Reply with only a decimal number."
    # )
    # raw = llm_client.generate(
    #     system_prompt="You are a strict, impartial evaluator.",
    #     user_message=judge_prompt,
    # )
    # try:
    #     return max(0.0, min(1.0, float(raw.strip())))
    # except ValueError:
    #     logger.error("information_accuracy: could not parse judge response: %r", raw)
    #     return 0.0

    return 0.5  # stub


def brand_voice_consistency(
    output: str,
    expected_output: str,  # noqa: ARG001
    llm_client: Any | None = None,
    **_: Any,
) -> bool:
    """Return True if ``output`` matches the Budget Guru brand voice.

    Brand voice criteria (young-adult-friendly tone):
    - Uses simple, friendly language.
    - Does not use excessively technical jargon without explanation.
    - Is encouraging, not fear-inducing.

    Intended LLM prompt (to be implemented):
        System: "You are a brand voice evaluator for a fintech app targeting young adults."
        User: "Does the following answer use friendly, simple language suitable for
               someone in their 20s? Reply with only 'yes' or 'no'.\\n{output}"

    Args:
        output: The model-generated answer to evaluate.
        expected_output: Not used for this evaluator (kept for interface consistency).
        llm_client: An instance of ``app.llm_client.LLMClient`` for the judge call.

    Returns:
        bool.  Returns True while stub is active.

    Datadog integration note:
        Tag the resulting span with ``ml_app=config.DD_LLMOBS_ML_APP`` so
        results are grouped correctly in the Experiments UI.
    """
    if llm_client is None:
        logger.warning("brand_voice_consistency: llm_client not provided, returning stub True")
        return True

    # [LLM-as-a-judge] Replace stub below with actual llm_client.generate() call
    # judge_prompt = (
    #     f"Answer to evaluate:\n{output}\n\n"
    #     "Is this answer written in a friendly, simple style suitable for "
    #     "someone in their 20s who is new to investing? Reply with only 'yes' or 'no'."
    # )
    # raw = llm_client.generate(
    #     system_prompt=(
    #         "You are a brand voice evaluator for a fintech app targeting young adults."
    #     ),
    #     user_message=judge_prompt,
    # ).strip().lower()
    # return raw.startswith("yes")

    return True  # stub


# ---------------------------------------------------------------------------
# Evaluator registry (used by the Experiments runner)
# ---------------------------------------------------------------------------

EVALUATORS: dict[str, Any] = {
    "exact_match": exact_match,
    "contains_keywords": contains_keywords,
    "information_accuracy": information_accuracy,
    "brand_voice_consistency": brand_voice_consistency,
}
