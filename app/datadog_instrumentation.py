"""Datadog APM and LLM Observability initialization for Budget Guru.

IMPORTANT: This module must be imported before any LLM library (openai, etc.)
so that ddtrace can patch them at import time. The correct order is:
  1. LLMObs.enable()   — registers the LLM integration hooks
  2. ddtrace.auto      — patches all supported libraries including openai
  3. import openai     — now patched and auto-traced
"""

import logging

from app.config import config

logger = logging.getLogger(__name__)


def init_tracer() -> None:
    """Initialize Datadog LLM Observability and APM tracer.

    Must be called before importing openai or any other LLM library.
    """
    if not config.DD_TRACE_ENABLED:
        logger.info("DD_TRACE_ENABLED=false — skipping Datadog tracer initialization.")
        return

    try:
        import ddtrace  # noqa: F401
    except ImportError:
        logger.warning("ddtrace not installed — APM tracing disabled.")
        return

    # ---------------------------------------------------------------------------
    # 1. LLM Observability must be enabled FIRST, before ddtrace.auto patches libs
    #    Reference: https://docs.datadoghq.com/llm_observability/setup/sdk/python/
    # ---------------------------------------------------------------------------
    if config.DD_LLMOBS_ENABLED:
        try:
            from ddtrace.llmobs import LLMObs  # type: ignore[import]

            LLMObs.enable(
                ml_app=config.DD_LLMOBS_ML_APP,
                api_key=config.DD_API_KEY if config.DD_LLMOBS_AGENTLESS_ENABLED else None,
                site=config.DD_SITE,
                agentless_enabled=config.DD_LLMOBS_AGENTLESS_ENABLED,
            )
            logger.info(
                "Datadog LLM Observability enabled. ml_app=%s agentless=%s",
                config.DD_LLMOBS_ML_APP,
                config.DD_LLMOBS_AGENTLESS_ENABLED,
            )
        except ImportError:
            logger.warning("ddtrace.llmobs not available — LLM Observability disabled.")
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to enable LLM Observability: %s", exc)
    else:
        logger.info("DD_LLMOBS_ENABLED=false — LLM Observability disabled.")

    # ---------------------------------------------------------------------------
    # 2. Patch all supported libraries (openai, httpx, fastapi, etc.) AFTER LLMObs
    # ---------------------------------------------------------------------------
    import ddtrace.auto  # noqa: F401

    logger.info("Datadog APM tracer initialized.")
