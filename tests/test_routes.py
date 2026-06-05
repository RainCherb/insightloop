"""HTTP route tests."""

from __future__ import annotations


def test_index_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "InsightLoop" in r.text


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["provider"] == "mock"


def test_provider_info(client):
    r = client.get("/api/provider")
    assert r.status_code == 200
    data = r.json()
    assert data["provider"] == "mock"


def test_analyze_endpoint_returns_payload(client):
    r = client.post("/api/analyze", json={"text": "Great product, love the new dashboard!"})
    assert r.status_code == 200
    data = r.json()
    assert data["sentiment"] in {"positive", "neutral", "negative"}
    assert 0 <= data["score"] <= 100
    assert 1 <= data["urgency"] <= 5
    assert isinstance(data["topics"], list)
    assert isinstance(data["suggested_actions"], list)


def test_write_routes_require_auth():
    from fastapi.testclient import TestClient

    from main import create_app

    with TestClient(create_app(), raise_server_exceptions=False) as c:
        r = c.post("/api/analyze", json={"text": "Great product"})
    assert r.status_code == 401


def test_write_routes_fail_closed_when_auth_is_not_configured(monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from main import create_app

    monkeypatch.setenv("INSIGHTLOOP_API_KEY", "")
    monkeypatch.setenv("ADMIN_PASSWORD", "")
    get_settings.cache_clear()

    with TestClient(create_app(), raise_server_exceptions=False) as c:
        r = c.post("/api/analyze", json={"text": "Great product"})
    assert r.status_code == 503
    assert "Write protection is not configured" in r.json()["detail"]


def test_write_routes_allow_api_key_header():
    from fastapi.testclient import TestClient

    from main import create_app

    with TestClient(create_app(), raise_server_exceptions=False) as c:
        r = c.post(
            "/api/analyze",
            headers={"X-InsightLoop-API-Key": "test-write-key"},
            json={"text": "Great product"},
        )
    assert r.status_code == 200


def test_browser_login_session_requires_csrf():
    from fastapi.testclient import TestClient

    from app.security import CSRF_COOKIE_NAME
    from main import create_app

    with TestClient(create_app(), raise_server_exceptions=False) as c:
        login = c.post(
            "/login",
            data={"username": "admin", "password": "test-admin-password"},
            follow_redirects=False,
        )
        assert login.status_code == 303

        missing = c.post("/api/analyze", json={"text": "Great product"})
        assert missing.status_code == 403

        csrf = c.cookies.get(CSRF_COOKIE_NAME)
        allowed = c.post(
            "/api/analyze",
            headers={"X-CSRF-Token": csrf},
            json={"text": "Great product"},
        )
        assert allowed.status_code == 200


def test_create_feedback_persists_and_returns(client):
    payload = {
        "text": "The export-to-PDF feature is amazing and saved us hours.",
        "source": "email",
        "customer_email": "happy@example.com",
    }
    r = client.post("/api/feedback", json=payload)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["text"] == payload["text"]
    assert data["analysis"] is not None
    assert data["analysis"]["sentiment"] in {"positive", "neutral", "negative"}


def test_list_feedback_filter(client):
    client.post("/api/feedback", json={"text": "Awesome product, love it!"})
    client.post("/api/feedback", json={"text": "Horrible, the app crashes constantly."})
    r = client.get("/api/feedback")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 2
    sentiments = {row["analysis"]["sentiment"] for row in rows if row["analysis"]}
    assert {"positive", "negative"} & sentiments


def test_get_and_delete_feedback(client):
    r = client.post("/api/feedback", json={"text": "Just a test item."})
    fid = r.json()["id"]
    g = client.get(f"/api/feedback/{fid}")
    assert g.status_code == 200
    d = client.delete(f"/api/feedback/{fid}")
    assert d.status_code == 204
    g2 = client.get(f"/api/feedback/{fid}")
    assert g2.status_code == 404


def test_bulk_upload_csv(client):
    csv = (
        "text,source,customer_email\n"
        '"First feedback: love it",email,a@x.com\n'
        '"Second: terrible support",support,b@x.com\n'
        '"Third: stable and fast",email,c@x.com\n'
    )
    r = client.post(
        "/api/feedback/bulk",
        files={"file": ("f.csv", csv, "text/csv")},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 3
    assert data["succeeded"] == 3
    assert data["failed"] == 0


def test_insights_summary(client):
    client.post("/api/feedback", json={"text": "Love the new dashboard and the speed!"})
    client.post("/api/feedback", json={"text": "The app crashes constantly, terrible."})
    r = client.get("/api/insights/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 2
    assert data["positive"] + data["neutral"] + data["negative"] == data["total"]


def test_reports_csv(client):
    client.post("/api/feedback", json={"text": "Just a test row."})
    r = client.get("/api/reports/csv")
    assert r.status_code == 200
    assert "text" in r.text
    assert r.headers["content-type"].startswith("text/csv")


def test_reports_pdf(client):
    client.post("/api/feedback", json={"text": "Just a test row."})
    r = client.get("/api/reports/pdf")
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"
