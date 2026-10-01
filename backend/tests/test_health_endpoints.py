from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers import health as health_module


class _HealthyQuery:
    def select(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return object()


class _HealthySupabase:
    def table(self, _name):
        return _HealthyQuery()


class _BrokenSupabase:
    def table(self, _name):
        raise RuntimeError("database unavailable")


def _client():
    app = FastAPI()
    app.include_router(health_module.router)
    return TestClient(app)


def test_liveness():
    response = _client().get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_checks_supabase(monkeypatch):
    monkeypatch.setattr(
        health_module,
        "get_admin_supabase_client",
        lambda: _HealthySupabase(),
    )
    response = _client().get("/health/ready")

    assert response.status_code == 200
    assert response.json()["dependencies"]["supabase"] == "ok"


def test_readiness_returns_503_when_supabase_is_down(monkeypatch):
    monkeypatch.setattr(
        health_module,
        "get_admin_supabase_client",
        lambda: _BrokenSupabase(),
    )
    response = _client().get("/health/ready")

    assert response.status_code == 503
