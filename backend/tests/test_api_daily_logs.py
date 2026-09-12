import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_daily_logs_repository,
)
from backend.api.main import app


class FakeDailyLogsRepository:
    def __init__(self):
        self.last_get = None
        self.last_upsert = None
        self.last_range = None

    def get_for_date_compatible(self, user_id, log_date):
        self.last_get = (user_id, str(log_date))
        return {
            "id": "daily-1",
            "date": str(log_date),
            "steps": 7000,
            "day_type": "Casa",
            "activity_plan": "Riposo",
        }

    def upsert_for_date(self, user_id, log_date, values):
        self.last_upsert = (user_id, str(log_date), values)
        return {"id": "daily-1", "date": str(log_date), **values}

    def list_date_range(self, user_id, start_date, end_date, columns=None):
        self.last_range = (user_id, str(start_date), str(end_date))
        return [
            {"date": "2026-08-21", "steps": 5000},
            {"date": "2026-08-22", "steps": 7000},
        ]


class FakeActivitiesRepository:
    def __init__(self):
        self.last_step_calories = None

    def list_for_date(
        self,
        user_id,
        log_date,
    ):
        return [
            {
                "activity_name": "Padel",
                "activity_type": "Padel",
                "duration_seconds": 3600,
                "estimated_steps": 6300,
                "burned_calories": 500,
            }
        ]

    def upsert_named_for_date(
        self,
        user_id,
        log_date,
        activity_name,
        burned_calories,
    ):
        self.last_step_calories = burned_calories

        return {
            "id": "steps-activity",
            "user_id": user_id,
            "date": str(log_date),
            "activity_name": activity_name,
            "burned_calories": burned_calories,
        }


fake_repo = FakeDailyLogsRepository()
fake_activities_repo = FakeActivitiesRepository()


def override_current_user():
    return CurrentUser(id="authenticated-user", access_token="fake-token")


def override_repo():
    return fake_repo


def override_activities_repo():
    return fake_activities_repo


@pytest.fixture(autouse=True)
def api_overrides():
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_daily_logs_repository] = override_repo
    app.dependency_overrides[get_activities_repository] = (
        override_activities_repo
    )
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_get_daily_log():
    r = client.get("/daily-logs/2026-08-22")
    assert r.status_code == 200


def test_update_daily_log_steps():
    r = client.patch(
        "/daily-logs/2026-08-22",
        json={"steps": 9000},
    )

    assert r.status_code == 200
    assert r.json()["movement"]["total_steps"] == 7000
    assert (
        r.json()["movement"][
            "estimated_training_steps"
        ]
        == 6300
    )
    assert (
        r.json()["movement"]["net_daily_steps"]
        == 700
    )
    assert (
        fake_activities_repo.last_step_calories
        == 28
    )


def test_update_daily_log_planning():
    r = client.patch(
        "/daily-logs/2026-08-22",
        json={"day_type": "Ufficio", "activity_plan": "Attiva"},
    )
    assert r.status_code == 200


def test_empty_update_rejected():
    r = client.patch("/daily-logs/2026-08-22", json={})
    assert r.status_code == 400


def test_negative_steps_rejected():
    r = client.patch("/daily-logs/2026-08-22", json={"steps": -1})
    assert r.status_code == 422


def test_invalid_weight_rejected():
    r = client.patch("/daily-logs/2026-08-22", json={"weight": 0})
    assert r.status_code == 422


def test_get_daily_logs_range():
    r = client.get(
        "/daily-logs",
        params={"start_date": "2026-08-21", "end_date": "2026-08-22"},
    )
    assert r.status_code == 200
    assert r.json()["count"] == 2


def test_invalid_range_rejected():
    r = client.get(
        "/daily-logs",
        params={"start_date": "2026-08-23", "end_date": "2026-08-22"},
    )
    assert r.status_code == 400


def test_planning_update_does_not_recalculate_steps():
    fake_activities_repo.last_step_calories = None

    response = client.patch(
        "/daily-logs/2026-08-22",
        json={
            "day_type": "Casa",
            "activity_plan": "Moderata",
        },
    )

    assert response.status_code == 200
    assert response.json()["movement"] is None
    assert fake_activities_repo.last_step_calories is None
