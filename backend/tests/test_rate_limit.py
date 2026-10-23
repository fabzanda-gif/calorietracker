from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.rate_limit import AIRateLimitMiddleware


def test_ai_rate_limit_blocks_after_minute_limit(monkeypatch):
    monkeypatch.setenv("AI_RATE_LIMIT_PER_MINUTE", "2")
    monkeypatch.setenv("AI_RATE_LIMIT_PER_DAY", "10")

    app = FastAPI()
    app.add_middleware(AIRateLimitMiddleware)

    @app.post("/meals/conversational/preview")
    def preview():
        return {"ok": True}

    client = TestClient(app)
    headers = {"Authorization": "Bearer test-token"}

    assert client.post(
        "/meals/conversational/preview",
        headers=headers,
    ).status_code == 200
    assert client.post(
        "/meals/conversational/preview",
        headers=headers,
    ).status_code == 200

    limited = client.post(
        "/meals/conversational/preview",
        headers=headers,
    )

    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) >= 1


def test_day_briefing_get_is_rate_limited(monkeypatch):
    monkeypatch.setenv("AI_RATE_LIMIT_PER_MINUTE", "1")
    monkeypatch.setenv("AI_RATE_LIMIT_PER_DAY", "10")

    app = FastAPI()
    app.add_middleware(AIRateLimitMiddleware)

    @app.get("/days/{day_date}/briefing")
    def briefing(day_date: str):
        return {"date": day_date}

    client = TestClient(app)
    headers = {"Authorization": "Bearer briefing-token"}

    assert client.get(
        "/days/2026-09-24/briefing",
        headers=headers,
    ).status_code == 200
    assert client.get(
        "/days/2026-09-24/briefing",
        headers=headers,
    ).status_code == 429
