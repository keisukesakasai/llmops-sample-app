"""Application configuration loaded from environment variables."""

import os


class Config:
    """Centralized configuration for Budget Guru."""

    # OpenAI / LLM
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str | None = os.getenv("OPENAI_BASE_URL") or None
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4.1")
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "30"))

    # Datadog
    DD_API_KEY: str = os.getenv("DD_API_KEY", "")
    DD_APP_KEY: str = os.getenv("DD_APP_KEY", "")
    DD_SITE: str = os.getenv("DD_SITE", "datadoghq.com")

    # Datadog LLM Observability
    DD_LLMOBS_ENABLED: bool = os.getenv("DD_LLMOBS_ENABLED", "false").lower() == "true"
    DD_LLMOBS_ML_APP: str = os.getenv("DD_LLMOBS_ML_APP", "budget-guru-ml-app")
    DD_LLMOBS_PROJECT_NAME: str = os.getenv("DD_LLMOBS_PROJECT_NAME", "budget-guru-experiments")
    DD_LLMOBS_AGENTLESS_ENABLED: bool = (
        os.getenv("DD_LLMOBS_AGENTLESS_ENABLED", "false").lower() == "true"
    )

    # Datadog Tracing
    DD_TRACE_ENABLED: bool = os.getenv("DD_TRACE_ENABLED", "true").lower() == "true"


config = Config()
