"""OpenAI Chat Completions adapter (works with any compatible model)."""

from __future__ import annotations

import json

from openai import OpenAI, OpenAIError

from app.ai.base import SYSTEM_PROMPT, LLMClient, LLMError, LLMResponse


class OpenAIClient(LLMClient):
    provider_name = "openai"

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise LLMError("OPENAI_API_KEY is not set")
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def analyze_feedback(self, text: str) -> LLMResponse:
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": self._build_user_prompt(text)},
                ],
            )
        except OpenAIError as exc:
            raise LLMError(f"OpenAI request failed: {exc}") from exc

        if not completion.choices:
            raise LLMError("OpenAI returned no choices")

        content = completion.choices[0].message.content or ""
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
