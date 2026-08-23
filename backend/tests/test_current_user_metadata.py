from types import SimpleNamespace

from fastapi.security import HTTPAuthorizationCredentials

from backend.api import dependencies


class FakeAuth:
    def get_user(self, token):
        return SimpleNamespace(
            user=SimpleNamespace(
                id="user-1",
                user_metadata={
                    "height": 180,
                    "goal_mode": "maintenance",
                },
            )
        )


class FakeSupabase:
    def __init__(self):
        self.auth = FakeAuth()


def test_current_user_exposes_supabase_user_metadata(monkeypatch):
    monkeypatch.setattr(
        dependencies,
        "get_supabase_client",
        lambda: FakeSupabase(),
    )

    user = dependencies.get_current_user(
        HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="token",
        )
    )

    assert user.id == "user-1"
    assert user.access_token == "token"
    assert user.metadata == {
        "height": 180,
        "goal_mode": "maintenance",
    }


def test_current_user_without_metadata_gets_empty_dict(monkeypatch):
    class NoMetadataAuth:
        def get_user(self, token):
            return SimpleNamespace(
                user=SimpleNamespace(
                    id="user-2",
                    user_metadata=None,
                )
            )

    fake = SimpleNamespace(auth=NoMetadataAuth())

    monkeypatch.setattr(
        dependencies,
        "get_supabase_client",
        lambda: fake,
    )

    user = dependencies.get_current_user(
        HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="token",
        )
    )

    assert user.metadata == {}
