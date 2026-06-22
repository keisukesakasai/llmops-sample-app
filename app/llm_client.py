"""LLM client abstraction for Budget Guru.

Wraps OpenAI-compatible Chat Completions API calls so that:
- The rest of the application never imports httpx directly.
- Datadog LLM Observability spans are emitted automatically via the
  ddtrace OpenAI integration (patched in datadog_instrumentation.py).
- The Experiments runner can reuse this client for offline evaluations.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"


class LLMClient:
    """Thin wrapper around an OpenAI-compatible Chat Completions endpoint."""

    def __init__(
        self,
        model_name: str,
        api_key: str,
        base_url: str | None = None,
        timeout: int = 30,
    ) -> None:
        """Initialize the LLM client.

        Args:
            model_name: Model identifier, e.g. ``"gpt-4.1"``.
            api_key: API key for the LLM provider.
            base_url: Optional custom base URL for OpenAI-compatible APIs.
                      Defaults to ``"https://api.openai.com"``.
            timeout: HTTP request timeout in seconds.
        """
        self.model_name = model_name
        self._api_key = api_key
        self._base_url = (base_url or "https://api.openai.com").rstrip("/")
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Generate a response from the LLM.

        This is the primary entry point used by both the FastAPI chat endpoint
        and the Experiments runner.  Datadog LLM Obs spans are created
        automatically by the ddtrace OpenAI integration around the underlying
        HTTP call.

        Args:
            system_prompt: System-level instruction for the model.
            user_message: The end-user's question or message.
            metadata: Optional key/value pairs forwarded as request metadata
                      (e.g. ``{"user_id": "u123", "prompt_variant": "P4"}``).

        Returns:
            The model's text reply.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        return self._call_chat_completions(messages, metadata=metadata)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _call_chat_completions(
        self,
        messages: list[dict[str, str]],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Send a request to the Chat Completions endpoint and return the reply.

        Isolating the actual HTTP call here makes it easy to:
        - Swap the underlying HTTP library (httpx → requests) in one place.
        - Add retry / circuit-breaker logic without touching business code.
        - Inject Datadog LLM Obs span annotations if needed.

        Args:
            messages: OpenAI-format message list.
            metadata: Optional metadata forwarded in the request body under
                      the ``"user"`` field (as a JSON-encoded string).

        Returns:
            The text content of the first choice.

        Raises:
            httpx.HTTPStatusError: On non-2xx responses.
            httpx.TimeoutException: When the request exceeds ``self._timeout``.
        """
        url = f"{self._base_url}{_CHAT_COMPLETIONS_PATH}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
        }
        if metadata:
            import json
            payload["user"] = json.dumps(metadata)

        logger.debug("Calling LLM: model=%s url=%s", self.model_name, url)

        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]
