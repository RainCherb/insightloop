# InsightLoop — AI Feedback Analytics

> **Self-hosted customer feedback analytics for SaaS, product, and support teams.**
> Turn reviews, support tickets, surveys, and app feedback into sentiment, topics, urgency, reports, and a live dashboard.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org)
[![CI](https://github.com/RainCherb/insightloop/actions/workflows/ci.yml/badge.svg)](https://github.com/RainCherb/insightloop/actions/workflows/ci.yml)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](#-contributing)

InsightLoop turns messy customer feedback into an actionable product signal. Paste a single review, upload a CSV, or call the REST API; InsightLoop analyzes every item, stores the result, and shows the trends your team should act on next.

Use it to triage customer support tickets, mine product reviews, summarize survey responses, watch churn risk, and build weekly voice-of-customer reports without sending your data to a hosted analytics platform. It is **self-hosted**, **small**, and **provider-agnostic** — bring OpenAI, Anthropic, local Ollama, or the built-in offline mock provider.

---

## Why InsightLoop?

- **Find urgent issues faster** — detect negative sentiment, high-urgency feedback, and repeated complaints before they pile up.
- **Make product decisions from real text** — extract topics, summaries, and suggested actions from reviews, NPS comments, emails, and helpdesk exports.
- **Keep control of your data** — run it locally or on your own server with SQLite/Postgres-compatible storage.
- **Avoid provider lock-in** — switch between OpenAI, Anthropic, Ollama, or deterministic mock mode with one environment variable.

---

## Features

- **AI sentiment analysis** — `positive`, `neutral`, or `negative`, plus a normalized `0–100` score.
- **Topic extraction** — tag repeated product issues, support themes, feature requests, pricing complaints, UX friction, and more.
- **Urgency scoring** — prioritize the feedback that needs a response first.
- **Suggested actions** — get concrete next steps for support, product, and customer success teams.
- **Live dashboard** — KPIs, sentiment distribution, top topics, daily trend line, and urgent item feed.
- **Bulk CSV upload** — analyze review exports, survey dumps, and support-ticket batches.
- **REST API** — integrate feedback ingestion into your product, CRM, helpdesk, or internal tools.
- **Reports** — export analyzed feedback as CSV, JSON, or a PDF summary.
- **Secure write access** — browser login + CSRF protection or API-key auth for mutating endpoints.
- **Docker-ready** — run with plain Python, Docker, or `docker compose`.
- **Typed and tested** — FastAPI, SQLAlchemy, Pydantic, pytest, ruff, and CI across Python 3.11–3.14.

## Best for

- SaaS customer feedback analysis
- App-store and marketplace review mining
- Support ticket triage
- NPS, CSAT, and survey comment analysis
- Product feedback dashboards
- Voice-of-customer reporting
- Self-hosted AI analytics prototypes

---

## 🚀 Quick start

### 1. Clone & install

```powershell
git clone https://github.com/RainCherb/insightloop.git
cd insightloop
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> 🪟 On Linux / macOS replace the venv activation with `source .venv/bin/activate`.

### 2. Configure

```powershell
Copy-Item .env.example .env
# Open .env and (optionally) set OPENAI_API_KEY
# Local demo without an LLM provider key:
#   set LLM_PROVIDER=mock
#   set ADMIN_PASSWORD to sign in at /login
#   set SESSION_SECRET to a long random string
```

### 3. Run

```powershell
python main.py
```

Open **http://localhost:8000**, sign in at **/login**, then try the *Demo* button on the **Analyze** page. It loads pre-canned feedback into the **Mock** provider so you can see the full flow.

### 4. Try the API

```powershell
curl.exe -X POST http://localhost:8000/api/feedback `
  -H "Authorization: Bearer $env:INSIGHTLOOP_API_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"text\":\"The dashboard is great but export to PDF crashes on large reports.\",\"source\":\"email\",\"customer_email\":\"alex@example.com\"}"
```

You will get a JSON object with `sentiment`, `score`, `topics`, `urgency`, `summary`, and `suggested_actions`.

---

## ⚙️ Configuration

All settings come from environment variables (or a `.env` file). See [`.env.example`](.env.example) for the full list.

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `openai` | `openai` \| `anthropic` \| `ollama` \| `mock` |
| `OPENAI_API_KEY` | _empty_ | Required when `LLM_PROVIDER=openai` |
| `OPENAI_MODEL` | `gpt-4o-mini` | Any chat-completions model |
| `ANTHROPIC_API_KEY` | _empty_ | Required when `LLM_PROVIDER=anthropic` |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5` | Any current Claude model |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama endpoint |
| `OLLAMA_MODEL` | `llama3.1:8b` | Any pulled Ollama model |
| `APP_HOST` | `0.0.0.0` | Bind address |
| `APP_PORT` | `8000` | Bind port |
| `APP_DEBUG` | `false` | Enables FastAPI debug mode |
| `INSIGHTLOOP_API_KEY` | _empty_ | Bearer/API key for mutating REST API calls |
| `ADMIN_USERNAME` | `admin` | Browser login username for mutating UI actions |
| `ADMIN_PASSWORD` | _empty_ | Browser login password; when empty, browser write actions are disabled |
| `SESSION_SECRET` | _empty_ | Signing secret for browser sessions; falls back to the admin password/API key |
| `SECURE_COOKIES` | `false` | Set `true` when serving only over HTTPS |
| `DATABASE_URL` | `sqlite:///./data/insightloop.db` | SQLAlchemy URL |

---

## 🧪 Demo mode

Set `LLM_PROVIDER=mock` in `.env` and start the app. The mock client produces **deterministic, plausible analyses** without an OpenAI/Anthropic/Ollama key — the same text always returns the same result. It’s perfect for:

- trying the app without signing up anywhere
- CI / unit tests
- offline development on a plane

Mutating actions are protected even in demo mode. Set `ADMIN_PASSWORD` for the
browser UI, or set `INSIGHTLOOP_API_KEY` and pass it as a Bearer token for REST
API calls.

A `data/sample_feedback.csv` with 60 realistic reviews is included — load it from the **Dashboard** page to populate the charts instantly.

---

## 🐳 Docker

```bash
docker build -t insightloop .
docker run --rm -p 8000:8000 --env-file .env -v ${PWD}/data:/app/data insightloop
```

Set `ADMIN_PASSWORD` and `SESSION_SECRET` in `.env` before using the browser UI.
A `docker-compose.yml` is provided for one-line spin-up.

---

## 📡 API reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/feedback` | Analyze a single feedback item |
| `POST` | `/api/feedback/bulk` | Upload a CSV, get per-row analyses |
| `GET`  | `/api/feedback` | List stored feedback (paginated, filterable) |
| `GET`  | `/api/insights/summary` | Aggregate KPIs |
| `GET`  | `/api/insights/trends` | Daily sentiment trend |
| `GET`  | `/api/insights/topics` | Top topics with counts |
| `GET`  | `/api/reports/csv` | Download all feedback as CSV |
| `GET`  | `/api/reports/json` | Download all feedback as JSON |
| `GET`  | `/api/reports/pdf` | Download a one-page PDF summary |
| `GET`  | `/health` | Liveness probe |
| `GET`  | `/api/provider` | Active LLM provider + model |

Full docs with examples: [`docs/API.md`](docs/API.md).

---

## 🏗️ Architecture

InsightLoop is a single FastAPI app with Jinja2 pages, JSON APIs, SQLAlchemy storage, and swappable LLM adapters. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full module map and data flow.

---

## 🧪 Testing

```bash
pip install -r requirements-dev.txt
pytest
```

Tests use the `mock` provider, so they require **no network or API key**.

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the repo & create a branch from `main`.
2. Install dev deps: `pip install -r requirements-dev.txt`.
3. Run the test suite: `pytest`.
4. Run the linter: `ruff check . && ruff format .`.
5. Open a PR — please use the [PR template](.github/pull_request_template.md).

Bug reports and feature requests: [open an issue](.github/ISSUE_TEMPLATE).

---

## 🗺️ Roadmap

- [ ] Multi-language feedback (auto-detect + analyze in EN/RU/ES)
- [ ] Webhook integration (auto-ingest from email / Slack / Helpdesk)
- [ ] Topic clustering (embeddings + k-means)
- [ ] Email digest of weekly insights
- [ ] Embeddable widget for collecting feedback on a site
- [ ] User accounts and multi-tenant workspaces

---

## 📜 License

[MIT](LICENSE) © 2026 RainCherb

---

## ⭐ Star history

If InsightLoop saved you time, a star on GitHub is appreciated ⭐
