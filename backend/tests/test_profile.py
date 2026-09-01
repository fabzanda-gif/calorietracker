from types import SimpleNamespace

from fastapi.security import HTTPAuthorizationCredentials

from backend.api import dependencies
from backend.api.routers import profile


def setup_function():
    dependencies._AUTH_CACHE.clear()


def test_get_profile_returns_current_metadata(monkeypatch):
    monkeypatch.setattr(
        dependencies,
        "get_current_user",
        lambda credentials=None: dependencies.CurrentUser(
            id="user-1",
            access_token="token",
            metadata={"height": 180, "goal_mode": "maintenance"},
        ),
    )

    user = dependencies.CurrentUser(
        id="user-1",
        access_token="token",
        metadata={"height": 180, "goal_mode": "maintenance"},
    )

    result = profile.get_profile(user)

    assert result == {
        "id": "user-1",
        "metadata": {
            "height": 180,
            "goal_mode": "maintenance",
        },
    }


def test_update_profile_sends_bearer_token_and_metadata(monkeypatch):
    captured = {}

    class FakeResponse:
        ok = True
        status_code = 200

        def json(self):
            return {
                "user": {
                    "id": "user-1",
                    "user_metadata": {
                        "height": 182,
                        "goal_mode": "loss",
                    },
                }
            }

    def fake_put(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(profile.requests, "put", fake_put)
    monkeypatch.setenv(
        "SUPABASE_URL",
        "https://example.supabase.co",
    )
    monkeypatch.setenv("SUPABASE_KEY", "test-key")

    user = dependencies.CurrentUser(
        id="user-1",
        access_token="secret-token",
        metadata={},
    )

    payload = profile.ProfileUpdate(
        height=182,
        goal_mode="loss",
    )

    result = profile.update_profile(payload, user)

    assert captured["url"] == (
        "https://example.supabase.co/auth/v1/user"
    )
    assert captured["headers"]["Authorization"] == (
        "Bearer secret-token"
    )
    assert captured["headers"]["apikey"] == "test-key"
    assert captured["json"] == {
        "data": {
            "height": 182,
            "goal_mode": "loss",
        }
    }
    assert result["metadata"] == {
        "height": 182,
        "goal_mode": "loss",
    }
