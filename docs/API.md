# InsightLoop — API reference

All endpoints are available at `http://localhost:8000` when running locally.
Interactive docs: <http://localhost:8000/docs> (Swagger UI) and
<http://localhost:8000/redoc> (ReDoc).

The OpenAPI schema is also served at `/openapi.json`.

## Health

### `GET /health`

```bash
curl http://localhost:8000/health
# {"status":"ok","provider":"mock"}
```

## Provider

### `GET /api/provider`

Returns the active LLM provider, the configured provider from env, and the
model name.

```bash
curl http://localhost:8000/api/provider
# {"provider":"openai","configured_provider":"openai","model":"gpt-4o-mini"}
```

## Analyze (preview, no save)

### `POST /api/analyze`

Analyzes a piece of text **without persisting**. Useful for live UI previews.

Request body:

```json
{
  "text": "The export to PDF is broken, please fix ASAP.",
  "source": "email",
  "customer_email": "alex@example.com"
}
```

`source` and `customer_email` are optional.

Response (200):

```json
{
  "sentiment": "negative",
  "score": 18.0,
  "topics": ["bug", "export", "support"],
  "urgency": 5,
  "summary": "Customer reports PDF export is broken and demands an urgent fix.",
  "suggested_actions": [
    "Reply within 24 hours with a personal apology",
    "Open a high-priority ticket and assign an owner",
    "Schedule a follow-up call to confirm resolution"
  ]
}
```

## Feedback (CRUD)

### `POST /api/feedback`

Analyzes **and** persists a feedback item.

```bash
curl -X POST http://localhost:8000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{"text":"The dashboard is amazing!","source":"email","customer_email":"a@x.com"}'
```

Returns `201` and the full `FeedbackOut` (including the nested analysis).

### `POST /api/feedback/bulk`

Upload a CSV file. The CSV **must** have a `text` column. Optional columns:
`source`, `customer_email`.

```bash
curl -X POST http://localhost:8000/api/feedback/bulk \
  -F "file=@data/sample_feedback.csv"
```

Response (200):

```json
{
  "total": 60,
  "succeeded": 60,
  "failed": 0,
  "errors": []
}
```

### `GET /api/feedback`

List stored feedback. Query parameters:

| Param | Type | Default | Description |
|---|---|---|---|
| `sentiment` | string | – | `positive` / `neutral` / `negative` |
| `topic` | string | – | match exact topic tag |
| `min_urgency` | int (1–5) | – | minimum urgency |
| `source` | string | – | source tag |
| `limit` | int | 100 | 1–500 |
| `offset` | int | 0 |  |

### `GET /api/feedback/{id}`

Returns a single item or 404.

### `DELETE /api/feedback/{id}`

Removes a single item. Returns `204` on success, `404` if not found.

## Insights

### `GET /api/insights/summary`

```json
{
  "total": 42,
  "positive": 18,
  "neutral": 12,
  "negative": 12,
  "average_score": 58.4,
  "average_urgency": 2.3,
  "urgent_count": 5,
  "top_topics": [
    {"topic": "ui", "count": 14},
    {"topic": "pricing", "count": 9}
  ]
}
```

### `GET /api/insights/trends?days=14`

Returns one row per day for the last `days` days (`1 ≤ days ≤ 90`).

```json
[
  {"date": "2026-05-22", "positive": 1, "neutral": 0, "negative": 0},
  ...
]
```

### `GET /api/insights/topics?limit=10`

Top topics with counts.

### `GET /api/insights/urgent?limit=20`

Returns the most recent items with urgency ≥ 4.

## Reports

| Endpoint | Format | Filename |
|---|---|---|
| `GET /api/reports/csv`  | `text/csv`     | `insightloop.csv` |
| `GET /api/reports/json` | `application/json` | `insightloop.json` |
| `GET /api/reports/pdf`  | `application/pdf`  | `insightloop-report.pdf` |

```bash
curl -OJ http://localhost:8000/api/reports/csv
curl -OJ http://localhost:8000/api/reports/json
curl -OJ http://localhost:8000/api/reports/pdf
```

## Errors

| Status | When |
|---|---|
| `400` | Bad request (e.g. CSV without `text` column, empty CSV) |
| `404` | Feedback id not found |
| `415` | Uploaded file is not UTF-8 text |
| `422` | Validation error (Pydantic) |
| `500` | Unexpected LLM failure (see logs) |
