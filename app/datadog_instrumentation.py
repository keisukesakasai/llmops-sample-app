"""Datadog APM and LLM Observability initialization for Budget Guru.

This module must be imported before FastAPI app creation so that
ddtrace can patch libraries (httpx, etc.) at import time.
"""

import logging

from app.config import config

logger = logging.getLogger(__name__)


def init_tracer() -> None:
    """Initialize Datadog APM tracer and LLM Observability.

    Call this once at application startup (before the FastAPI app is created).
    It reads all configuration from environment variables via `config`.
    """
    if not config.DD_TRACE_ENABLED:
        logger.info("DD_TRACE_ENABLED=false — skipping Datadog tracer initialization.")
        return

    # ---------------------------------------------------------------------------
    # 1. Standard APM tracing
    #    ddtrace.patch_all() instruments common libraries (requests, httpx, etc.)
    #    automatically. Spans will be sent to the Datadog Agent (or agentless).
    # ---------------------------------------------------------------------------
    try:
        import ddtrace  # noqa: F401
        from ddtrace import tracer

        tracer.configure(
            # When DD_LLMOBS_AGENTLESS_ENABLED=true the SDK sends directly to
            # the Datadog intake endpoint without a local Agent.
            # Otherwise traces are forwarded via the local Datadog Agent.
        )

        import ddtrace.auto  # noqa: F401 — patches supported libraries

        logger.info("Datadog APM tracer initialized.")
    except ImportError:
        logger.warning("ddtrace not installed — APM tracing disabled.")
        return

    # ---------------------------------------------------------------------------
    # 2. LLM Observability (Agent Observability)
    #    Reference: https://docs.datadoghq.com/llm_observability/setup/sdk/python/
    #
    #    The recommended way is to call LLMObs.enable() with the relevant params.
    #    All parameters are read from environment variables when not passed
    #    explicitly, but we pass them explicitly here for clarity.
    # ---------------------------------------------------------------------------
    if not config.DD_LLMOBS_ENABLED:
        logger.info("DD_LLMOBS_ENABLED=false — LLM Observability disabled.")
        return

    try:
        # [Datadog LLM Obs SDK] Import the LLMObs class from ddtrace
        from ddtrace.llmobs import LLMObs  # type: ignore[import]

        LLMObs.enable(
            ml_app=config.DD_LLMOBS_ML_APP,
            # api_key is required only in agentless mode
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
