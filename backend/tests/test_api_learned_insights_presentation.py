import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_daily_logs_repository,
    get_meals_repository,
)
from backend.api.main import app


class FakeDailyLogsRepository:
    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
        columns=None,
    ):
        return [
            {
                "date": "2026-08-04",
                "day_type": "Ufficio",
                "activity_plan": "Attiva",
            },
            {
                "date": "2026-08-11",
                "day_type": "Ufficio",
                "activity_plan": "Attiva",
            },
            {
                "date": "2026-08-18",
                "day_type": "Ufficio",
                "activity_plan": "Attiva",
            },
            {
                "date": "2026-08-25",
                "day_type": "Ufficio",
                "activity_plan": "Attiva",
            },
        ]


class FakeMealsRepository:
    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
        columns=None,
    ):
        return [
            {
                "date": d,
                "meal_type": "Colazione",
                "name": "Colazione Ufficio",
                "calories": 310,
                "protein": 18,
                "carbs": 36,
                "fat": 10,
            }
            for d in [
                "2026-08-04",
                "2026-08-11",
                "2026-08-18",
                "2026-08-25",
            ]
        ]


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
    )


@pytest.fixture(autouse=True)
def api_overrides():
    app.dependency_overrides[get_current_user] = (
        override_current_user
    )
    app.dependency_overrides[get_daily_logs_repository] = (
        lambda: FakeDailyLogsRepository()
    )
    app.dependency_overrides[get_meals_repository] = (
        lambda: FakeMealsRepository()
    )

    yield

    app.dependency_overrides.clear()


client = TestClient(app)


def test_learned_endpoint_includes_presentation_cards():
    response = client.get(
        "/insights/learned",
        params={"on_date": "2026-09-01"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert "presentation" in payload
    assert payload["presentation"]["generated_for"] == "2026-09-01"

    cards = payload["presentation"]["learned"]

    assert any(
        card["title"] == "Martedì → Ufficio"
        and card["icon"] == "calendar"
        for card in cards
    )

    assert any(
        card["title"] == "Martedì → Attiva"
        and card["icon"] == "activity"
        for card in cards
    )

    assert any(
        card["title"]
        == "Martedì · Colazione → Colazione Ufficio"
        and card["icon"] == "meal"
        for card in cards
    )


def test_structured_payload_is_still_preserved():
    response = client.get(
        "/insights/learned",
        params={"on_date": "2026-09-01"},
    )

    payload = response.json()

    assert "learned" in payload
    assert "learning" in payload
    assert "presentation" in payload

    assert any(
        item["kind"] == "day_context"
        and item["value"] == "Ufficio"
        for item in payload["learned"]
    )


def test_presentation_keeps_raw_insight_for_explainability():
    response = client.get(
        "/insights/learned",
        params={"on_date": "2026-09-01"},
    )

    cards = response.json()["presentation"]["learned"]

    context_card = next(
        card
        for card in cards
        if card["kind"] == "day_context"
    )

    assert context_card["raw"]["value"] == "Ufficio"
    assert context_card["raw"]["confidence_level"] == "high"
