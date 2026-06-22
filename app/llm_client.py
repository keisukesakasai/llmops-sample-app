"""LLM client abstraction for Budget Guru.

Uses the official openai SDK so that ddtrace's OpenAI integration can
automatically create LLM Observability spans (prompts, tokens, latency).
"""

from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMClient:
    """Thin wrapper around an OpenAI-compatible Chat Completions endpoint."""

    def __init__(
        self,
        model_name: str,
        api_key: str,
        base_url: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.model_name = model_name
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url or None,
            timeout=timeout,
        )

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Generate a response from the LLM.

        ddtrace patches the openai SDK at startup, so each call here
        automatically produces an LLM Observability span containing the
        prompt, completion, token counts, and latency.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        logger.debug("Calling LLM: model=%s", self.model_name)
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=messages,  # type: ignore[arg-type]
            user=str(metadata) if metadata else None,
        )
        return response.choices[0].message.content or ""
