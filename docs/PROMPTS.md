# InsightLoop — Prompts

All providers receive the same system prompt. The user prompt wraps the raw
feedback in a fenced block and asks the model to emit a JSON object matching a
fixed schema.

## System prompt

```
You are InsightLoop, an expert customer-feedback analyst.
You always respond with a single JSON object that matches this exact schema:
{
  "sentiment": "positive" | "neutral" | "negative",
  "score": number between 0 and 100,    // 0 = extremely negative, 100 = extremely positive
  "topics": array of 1-5 short lowercase topic tags, e.g. ["pricing", "ui", "support"],
  "urgency": integer 1-5,                // 5 = requires immediate attention
  "summary": one concise sentence (<= 200 chars),
  "suggested_actions": array of 1-3 short, concrete, actionable next steps
}
Never add prose, markdown, or code fences around the JSON.
```

## User prompt template

```
Analyze the following customer feedback and respond with the JSON object
described in the system message.

FEEDBACK:
"""
{text}
"""
```

## Why this shape

- **One system prompt for all providers** keeps behaviour consistent and lets
  us A/B test models without re-prompting.
- **Strict JSON schema** — OpenAI gets `response_format={"type":"json_object"}`,
  Anthropic gets a tool definition with the same shape, Ollama gets
  `format: "json"`. The base-class parser (`LLMClient.parse_payload`) handles
  every other edge case (code fences, trailing text, etc.).
- **Suggested actions** are deliberately concrete (reply / open ticket / call)
  so the response is useful out of the box, not just descriptive.

## Iterating on the prompt

- The system prompt lives in `app/ai/base.py` as `SYSTEM_PROMPT`.
- The user prompt builder is `LLMClient._build_user_prompt`.
- The parser (`LLMClient.parse_payload`) clamps out-of-range values — change
  it if you add new fields with new ranges.
- Always re-run the test suite (`pytest`) after touching the prompt.

## Privacy note

When using a third-party provider (OpenAI / Anthropic), the feedback text is
sent to that provider over HTTPS. If you handle sensitive customer data:

- prefer a local Ollama model (`LLM_PROVIDER=ollama`), or
- run behind a VPN / VPC and configure egress allow-lists, or
- pre-process feedback to remove PII before calling `/api/feedback`.
