# InsightLoop

> **AI-powered customer feedback analyzer for small businesses.**
> Drop in reviews. Get sentiment, topics, urgency, and a live dashboard.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org)
[![CI](https://github.com/RainCherb/insightloop/actions/workflows/ci.yml/badge.svg)](https://github.com/RainCherb/insightloop/actions/workflows/ci.yml)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](#-contributing)

InsightLoop turns scattered customer feedback — review snippets, support tickets, survey comments, email replies — into structured intelligence you can act on. Paste a single review, upload a CSV, or hit the REST API; InsightLoop returns clean JSON *and* renders a dashboard with trends, top topics, and urgent items.

It is **self-hosted**, **small**, and **provider-agnostic** — works with OpenAI, Anthropic, a local Ollama model, or a built-in mock that requires no provider API key.

---

## ✨ Features

- 🔍 **Per-feedback analysis** — sentiment (`positive` / `neutral` / `negative`), score `0–100`, topic tags, urgency `1–5`, a one-line summary, and concrete suggested actions.
- 📊 **Live dashboard** — KPIs, sentiment distribution, top topics, daily trend line, urgent items feed.
- 📥 **Bulk CSV upload** — process dozens or thousands of feedback rows in one shot, with per-row progress.
- 🧠 **Provider-agnostic LLM** — swap between OpenAI, Anthropic, Ollama, or the offline **Mock** provider with a single env var.
- 🧪 **Demo mode** — analyzes feedback without a provider API key via the deterministic mock client; write actions still require a local admin password or API key.
- 📤 **Reports** — export results as CSV, JSON, or a polished PDF summary.
- 🔌 **REST API** — `POST /api/feedback`, `POST /api/feedback/bulk`, `GET /api/insights/summary`, `GET /api/reports/...`.
- 🎨 **Clean UI** — Tailwind + Alpine.js + Chart.js, no build step.
- 🐳 **Docker-ready** — one-command deployable.
- 🧰 **Typed & tested** — `pydantic` end-to-end, `pytest` suite, `ruff`-clean.

---

## 🏗️ Architecture

```
                ┌────────────────┐
                │  Browser (UI)  │   Tailwind + Alpine + Chart.js
                └──────┬─────────┘
                       │  HTTP / fetch
                       ▼
              ┌──────────────────┐
              │  FastAPI app     │   Jinja2 templates + JSON API
              │  (app/routes)    │
              └──┬───────────────┘
                 │
   ┌─────────────┼─────────────┐
   ▼             ▼             ▼
┌────────┐  ┌──────────┐  ┌────────────┐
│ Analyz │  │ Services │  │ Templates  │
│  er    │  │ insights │  │  (Jinja2)  │
│        │  │ reports  │  │            │
└───┬────┘  └────┬─────┘  └────────────┘
    │            │
    ▼            ▼
┌────────┐  ┌──────────┐
│ AI CLI │  │ SQLAlch. │
│  ents  │  │  SQLite  │
└───┬────┘  └──────────┘
    │
    ▼
 OpenAI / Anthropic / Ollama / Mock
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full picture.

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
- [ ] Auth & multi-tenant support

---

## 📜 License

[MIT](LICENSE) © 2026 RainCherb

---

## ⭐ Star history

If InsightLoop saved you time, a star on GitHub is appreciated ⭐
