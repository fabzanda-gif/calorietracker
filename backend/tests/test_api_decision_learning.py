import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_decision_selections_repository,
)
from backend.api.main import app


class FakeDecisionSelectionsRepository:
    def __init__(self):
        self.last_limit = None

    def list_for_user(self, user_id, *, limit=100):
        self.last_limit = limit

        return [
            {
                "mode": "order",
                "lens": "taste",
                "candidate": {
                    "source": "delivery",
                    "generic_fallback": False,
                },
            },
            {
                "mode": "order",
                "lens": "taste",
                "candidate": {
                    "source": "delivery",
                    "generic_fallback": False,
                },
            },
            {
                "mode": "order",
                "lens": "balanced",
                "candidate": {
                    "source": "takeaway",
                    "generic_fallback": False,
                },
            },
        ]


repo = FakeDecisionSelectionsRepository()


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
    )


@pytest.fixture(autouse=True)
def overrides():
    repo.last_limit = None

    app.dependency_overrides[get_current_user] = (
        override_current_user
    )
    app.dependency_overrides[
        get_decision_selections_repository
    ] = lambda: repo

    yield

    app.dependency_overrides.clear()


client = TestClient(app)


def test_decision_preferences_route_is_registered():
    assert (
        "/insights/decision-preferences"
        in app.openapi()["paths"]
    )


def test_decision_preferences_endpoint_returns_learned_profile():
    response = client.get(
        "/insights/decision-preferences"
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["user_id"] == "authenticated-user"
    assert payload["selection_count"] == 3

    assert payload["profile"]["mode"]["preferred"] == "order"
    assert payload["profile"]["mode"]["state"] == "learned"

    assert payload["profile"]["lens"]["preferred"] == "taste"
    assert payload["profile"]["source"]["preferred"] == "delivery"


def test_limit_is_forwarded_to_repository():
    response = client.get(
        "/insights/decision-preferences",
        params={"limit": 50},
    )

    assert response.status_code == 200
    assert repo.last_limit == 50
    assert response.json()["event_limit"] == 50


def test_limit_validation_rejects_zero():
    response = client.get(
        "/insights/decision-preferences",
        params={"limit": 0},
    )

    assert response.status_code == 422
