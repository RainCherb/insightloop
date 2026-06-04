"""Ollama (local LLM) adapter over its /api/chat HTTP endpoint."""

from __future__ import annotations

import json

import httpx

from app.ai.base import SYSTEM_PROMPT, LLMClient, LLMError, LLMResponse


class OllamaClient(LLMClient):
    provider_name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: float = 60.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    def analyze_feedback(self, text: str) -> LLMResponse:
        url = f"{self._base_url}/api/chat"
        payload = {
            "model": self._model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self._build_user_prompt(text)},
            ],
        }
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"Ollama request failed: {exc}") from exc

        message = data.get("message") or {}
        content = message.get("content")
        if not content:
            raise LLMError("Ollama response did not contain message.content")

        try:
            raw = json.loads(content)
        except json.JSONDecodeError:
            raw = self.parse_payload(content)
        parsed = self.parse_payload(raw)

        return LLMResponse(
            **parsed,
            raw=raw if isinstance(raw, dict) else {"content": content},
            provider=self.provider_name,
            model=self._model,
        )
