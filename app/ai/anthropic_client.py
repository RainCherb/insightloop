"""Anthropic Messages adapter using tool-use for guaranteed JSON."""

from __future__ import annotations

from typing import Any

from anthropic import Anthropic, AnthropicError

from app.ai.base import SYSTEM_PROMPT, LLMClient, LLMError, LLMResponse

ANALYSIS_TOOL: dict[str, Any] = {
    "name": "submit_feedback_analysis",
    "description": "Submit the structured analysis of one customer-feedback item.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sentiment": {
                "type": "string",
                "enum": ["positive", "neutral", "negative"],
            },
            "score": {
                "type": "number",
                "minimum": 0,
                "maximum": 100,
                "description": "0 = extremely negative, 100 = extremely positive.",
            },
            "topics": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 5,
            },
            "urgency": {"type": "integer", "minimum": 1, "maximum": 5},
            "summary": {"type": "string", "maxLength": 200},
            "suggested_actions": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 3,
            },
        },
        "required": [
            "sentiment",
            "score",
            "topics",
            "urgency",
            "summary",
            "suggested_actions",
        ],
    },
}


class AnthropicClient(LLMClient):
    provider_name = "anthropic"

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        self._client = Anthropic(api_key=api_key)
        self._model = model

    def analyze_feedback(self, text: str) -> LLMResponse:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=512,
                system=SYSTEM_PROMPT,
                tools=[ANALYSIS_TOOL],
                tool_choice={"type": "tool", "name": ANALYSIS_TOOL["name"]},
                messages=[
                    {
                        "role": "user",
                        "content": self._build_user_prompt(text),
                    }
                ],
            )
        except AnthropicError as exc:
            raise LLMError(f"Anthropic request failed: {exc}") from exc

        tool_input: dict[str, Any] | None = None
        for block in response.content:
            if (
                getattr(block, "type", None) == "tool_use"
                and getattr(block, "name", None) == ANALYSIS_TOOL["name"]
            ):
                tool_input = block.input
                break

        if tool_input is None:
            # Fall back: try to parse any text the model produced.
            text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
            if not text_blocks:
                raise LLMError("Anthropic response did not include tool input or text")
            tool_input = self.parse_payload("\n".join(text_blocks))

        parsed = self.parse_payload(tool_input)
        return LLMResponse(
            **parsed,
            raw=tool_input if isinstance(tool_input, dict) else {},
            provider=self.provider_name,
            model=self._model,
        )
