# InsightLoop — Deployment

InsightLoop is a single FastAPI process. You can run it directly, behind a
process manager, inside Docker, or on a PaaS.

## 1. Direct (development / laptop)

```bash
python -m venv .venv
source .venv/bin/activate          # or: .\.venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt
cp .env.example .env               # then edit OPENAI_API_KEY
python main.py
```

Open <http://localhost:8000>.

## 2. systemd (Linux server)

`/etc/systemd/system/insightloop.service`:

```ini
[Unit]
Description=InsightLoop
After=network.target

[Service]
Type=simple
User=insightloop
WorkingDirectory=/srv/insightloop
EnvironmentFile=/srv/insightloop/.env
ExecStart=/srv/insightloop/.venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now insightloop
sudo systemctl status insightloop
```

## 3. Docker (single container)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV APP_HOST=0.0.0.0 APP_PORT=8000
EXPOSE 8000
CMD ["python", "main.py"]
```

```bash
docker build -t insightloop .
docker run -d --name insightloop -p 8000:8000 --env-file .env -v insightloop-data:/app/data insightloop
```

## 4. docker-compose

`docker-compose.yml`:

```yaml
services:
  web:
    build: .
    image: insightloop:latest
    env_file: .env
    ports: ["8000:8000"]
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

```bash
docker compose up -d --build
```

## 5. Render / Railway / Fly.io

- Build command: `pip install -r requirements.txt`
- Start command: `python main.py`
- Set the environment variables from `.env.example` in the dashboard.
- Provision a persistent disk and mount it at `/app/data` if you need to
  keep the SQLite file across deploys (otherwise use a managed Postgres and
  point `DATABASE_URL` at it).

## 6. Reverse proxy (nginx)

```nginx
server {
    listen 80;
    server_name insight.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Add HTTPS with `certbot --nginx`.

## 7. Production checklist

- [ ] Set a strong random `SECRET_KEY` if you add auth
- [ ] Set `INSIGHTLOOP_API_KEY` for REST writes and/or `ADMIN_PASSWORD` for browser UI writes
- [ ] Set `SESSION_SECRET` to a strong random value
- [ ] Set `SECURE_COOKIES=true` when serving over HTTPS
- [ ] Move SQLite to Postgres (`DATABASE_URL=postgresql+psycopg://…`)
- [ ] Run behind nginx / Caddy / a load balancer
- [ ] Mount a persistent volume for the `data/` directory
- [ ] Configure structured logging (e.g. `loguru`, `structlog`)
- [ ] Add a real process manager (systemd / supervisord / Docker restart)
- [ ] Set up backups for the database
- [ ] Add monitoring (Prometheus `/metrics`, Sentry for errors)
- [ ] Pin all versions (already pinned in `requirements.txt`)
- [ ] Set `APP_DEBUG=false`
