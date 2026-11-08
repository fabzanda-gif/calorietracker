from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.api.dependencies import CurrentUser, get_current_user

from backend.rate_limit import AIRateLimitMiddleware
from types import SimpleNamespace
from fastapi import HTTPException
from backend import rate_limit


def test_ai_rate_limit_blocks_after_minute_limit(monkeypatch):
    monkeypatch.setenv("AI_RATE_LIMIT_PER_MINUTE", "2")
    monkeypatch.setenv("AI_RATE_LIMIT_PER_DAY", "10")

    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser("user-1", "token")
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
    app.dependency_overrides[get_current_user] = lambda: CurrentUser("user-1", "token")
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


def test_refreshed_tokens_share_user_quota_but_other_users_do_not(monkeypatch):
    monkeypatch.setenv("AI_RATE_LIMIT_PER_MINUTE", "1")
    app = FastAPI()
    identity = [CurrentUser("source", "token", authenticated_id="demo-user", read_only=True)]
    app.dependency_overrides[get_current_user] = lambda: identity[0]
    app.add_middleware(AIRateLimitMiddleware)
    @app.post("/meals/conversational/preview")
    def preview():
        return {"ok": True}
    client = TestClient(app)
    path = "/meals/conversational/preview"
    assert client.post(path, headers={"Authorization": "Bearer old"}).status_code == 200
    assert client.post(path, headers={"Authorization": "Bearer refreshed"}).status_code == 429
    identity[0] = CurrentUser("source", "token", authenticated_id="source")
    assert client.post(path).status_code == 200


def test_invalid_identity_is_rejected_before_any_ai_call(monkeypatch):
    app = FastAPI()
    def invalid():
        raise HTTPException(status_code=401, detail="Invalid token")
    app.dependency_overrides[get_current_user] = invalid
    app.add_middleware(AIRateLimitMiddleware)
    @app.post("/meals/conversational/preview")
    def preview():
        raise AssertionError("Unauthenticated request reached AI")
    assert TestClient(app).post("/meals/conversational/preview").status_code == 401


def test_shared_store_receives_verified_user_and_survives_new_middleware(monkeypatch):
    monkeypatch.setenv("AI_RATE_LIMIT_BACKEND", "supabase")
    calls = []
    def rpc(name, params):
        calls.append((name, params))
        return SimpleNamespace(execute=lambda: SimpleNamespace(data={
            "allowed": len(calls) == 1, "retry_after": 60 if len(calls) > 1 else 0,
        }))
    monkeypatch.setattr(rate_limit, "get_admin_supabase_client", lambda: SimpleNamespace(rpc=rpc))
    first = AIRateLimitMiddleware(FastAPI())
    restarted = AIRateLimitMiddleware(FastAPI())
    assert first._check_limit("verified-user") == (True, 0)
    assert restarted._check_limit("verified-user") == (False, 60)
    assert all(params["p_user_id"] == "verified-user" for _, params in calls)


def test_shared_store_failure_blocks_ai_instead_of_bypassing_quota(monkeypatch):
    monkeypatch.setenv("AI_RATE_LIMIT_BACKEND", "supabase")
    def unavailable():
        raise RuntimeError("database down")
    monkeypatch.setattr(rate_limit, "get_admin_supabase_client", unavailable)
    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser("user", "token")
    app.add_middleware(AIRateLimitMiddleware)
    @app.post("/meals/conversational/preview")
    def preview():
        raise AssertionError("Rate limiter failure reached AI")
    response = TestClient(app).post("/meals/conversational/preview")
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"
