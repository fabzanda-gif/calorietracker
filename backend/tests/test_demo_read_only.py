import pytest
from fastapi.testclient import TestClient

from backend.api import dependencies
from backend.api import main as api_main


client = TestClient(api_main.app)


def test_demo_identity_reads_source_metadata(monkeypatch):
    monkeypatch.setenv(
        "DEMO_ACCOUNT_USER_ID",
        "demo-user",
    )
    monkeypatch.setenv(
        "DEMO_SOURCE_USER_ID",
        "source-user",
    )
    monkeypatch.setattr(
        dependencies,
        "_source_user_metadata",
        lambda source_id: {
            "name": "Fabio",
            "source": source_id,
        },
    )

    effective_id, metadata, read_only = (
        dependencies._resolved_identity(
            "demo-user",
            {"name": "Demo"},
        )
    )

    assert effective_id == "source-user"
    assert metadata == {
        "name": "Fabio",
        "source": "source-user",
    }
    assert read_only is True


def test_regular_identity_is_unchanged(monkeypatch):
    monkeypatch.setenv(
        "DEMO_ACCOUNT_USER_ID",
        "demo-user",
    )
    monkeypatch.setenv(
        "DEMO_SOURCE_USER_ID",
        "source-user",
    )

    effective_id, metadata, read_only = (
        dependencies._resolved_identity(
            "regular-user",
            {"name": "Regular"},
        )
    )

    assert effective_id == "regular-user"
    assert metadata == {"name": "Regular"}
    assert read_only is False


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/meals"),
        ("PUT", "/profile"),
        ("PATCH", "/daily-logs/2026-09-09"),
        ("DELETE", "/profile/account"),
    ],
)
def test_demo_mutations_are_blocked_before_routes(
    monkeypatch,
    method,
    path,
):
    monkeypatch.setenv(
        "DEMO_ACCOUNT_USER_ID",
        "demo-user",
    )
    monkeypatch.setenv(
        "DEMO_SOURCE_USER_ID",
        "source-user",
    )
    monkeypatch.setattr(
        api_main,
        "get_current_user",
        lambda credentials: dependencies.CurrentUser(
            id="source-user",
            authenticated_id="demo-user",
            access_token=credentials.credentials,
            metadata={"name": "Fabio"},
            read_only=True,
        ),
    )

    response = client.request(
        method,
        path,
        headers={
            "Authorization": "Bearer demo-token",
        },
        json={},
    )

    assert response.status_code == 403
    assert "sola lettura" in response.json()["detail"]
