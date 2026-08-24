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
        # Four Tuesdays with the same context/activity.
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
                "date": "2026-08-04",
                "meal_type": "Colazione",
                "name": "Colazione Ufficio",
                "calories": 300,
                "protein": 17,
                "carbs": 35,
                "fat": 9,
            },
            {
                "date": "2026-08-11",
                "meal_type": "Colazione",
                "name": "Colazione Ufficio",
                "calories": 310,
                "protein": 18,
                "carbs": 36,
                "fat": 10,
            },
            {
                "date": "2026-08-18",
                "meal_type": "Colazione",
                "name": "Colazione Ufficio",
                "calories": 320,
                "protein": 19,
                "carbs": 37,
                "fat": 11,
            },
            {
                "date": "2026-08-25",
                "meal_type": "Colazione",
                "name": "Colazione Ufficio",
                "calories": 310,
                "protein": 18,
                "carbs": 36,
                "fat": 10,
            },
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


def test_learned_insights_route_is_registered():
    assert (
        "/insights/learned"
        in app.openapi()["paths"]
    )


def test_learned_insights_endpoint_returns_structured_patterns():
    response = client.get(
        "/insights/learned",
        params={"on_date": "2026-09-01"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["generated_for"] == "2026-09-01"
    assert payload["learned_count"] >= 3

    learned = payload["learned"]

    assert any(
        item["kind"] == "day_context"
        and item["weekday_name"] == "Tuesday"
        and item["value"] == "Ufficio"
        and item["confidence_level"] == "high"
        for item in learned
    )

    assert any(
        item["kind"] == "activity_plan"
        and item["weekday_name"] == "Tuesday"
        and item["value"] == "Attiva"
        and item["confidence_level"] == "high"
        for item in learned
    )

    assert any(
        item["kind"] == "meal"
        and item["meal_type"] == "Colazione"
        and item["value"] == "Colazione Ufficio"
        and item["day_context"] == "Ufficio"
        for item in learned
    )


def test_low_or_missing_evidence_is_not_promoted_to_learned():
    response = client.get(
        "/insights/learned",
        params={"on_date": "2026-09-01"},
    )

    assert response.status_code == 200
    payload = response.json()

    # Only Tuesday has enough evidence in these fakes.
    assert not any(
        item["weekday_name"] != "Tuesday"
        for item in payload["learned"]
    )
