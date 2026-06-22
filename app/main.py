"""Budget Guru – FastAPI application entry point.

Initialize Datadog tracing *before* importing FastAPI so that ddtrace can
patch all supported libraries at import time.
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

# Datadog must be initialized first
from app.datadog_instrumentation import init_tracer

init_tracer()

from typing import Optional  # noqa: E402

from fastapi import FastAPI, HTTPException  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from app.config import config  # noqa: E402
from app.llm_client import LLMClient  # noqa: E402
from app.prompts import get_system_prompt  # noqa: E402

app = FastAPI(
    title="Budget Guru",
    description="LLMOps sample app – investment assistant for young adults.",
    version="0.1.0",
)

# Single shared LLM client instance (thread-safe with httpx)
_llm_client = LLMClient(
    model_name=config.LLM_MODEL,
    api_key=config.OPENAI_API_KEY,
    base_url=config.OPENAI_BASE_URL,
    timeout=config.LLM_TIMEOUT,
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Body for POST /chat."""

    user_id: str
    message: str
    prompt_variant: Optional[str] = "P1"


class ChatResponse(BaseModel):
    """Response from POST /chat."""

    answer: str
    prompt_variant: str
    model: str


class HealthResponse(BaseModel):
    """Response from GET /health."""

    status: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["ops"])
def health_check() -> HealthResponse:
    """Liveness check – returns ``{"status": "ok"}``."""
    return HealthResponse(status="ok")


@app.post("/chat", response_model=ChatResponse, tags=["chat"])
def chat(request: ChatRequest) -> ChatResponse:
    """Generate an investment-related answer for the given user message.

    The ``prompt_variant`` field selects the system prompt (P1–P4) used for
    this request, enabling A/B comparison of prompt strategies in Datadog
    LLM Observability.

    Datadog LLM Obs automatically traces the underlying LLM call because
    ``init_tracer()`` patches the HTTP client at startup.
    """
    variant = (request.prompt_variant or "P1").upper()
    system_prompt = get_system_prompt(variant)

    metadata = {
        "user_id": request.user_id,
        "prompt_variant": variant,
    }

    try:
        answer = _llm_client.generate(
            system_prompt=system_prompt,
            user_message=request.message,
            metadata=metadata,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {exc}") from exc

    return ChatResponse(
        answer=answer,
        prompt_variant=variant,
        model=config.LLM_MODEL,
    )
