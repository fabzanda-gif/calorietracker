from fastapi.testclient import TestClient

from backend.api.dependencies import CurrentUser, get_current_user
from backend.api.main import app
from backend.api.routers.daily_logs import get_daily_logs_repository


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
        self.last_upsert = (
            user_id,
            str(log_date),
            values,
        )
        return {
            "id": "daily-1",
            "date": str(log_date),
            **values,
        }

    def list_date_range(self, user_id, start_date, end_date, columns=None):
        self.last_range = (
            user_id,
            str(start_date),
            str(end_date),
        )
        return [
            {
                "date": "2026-08-21",
                "steps": 5000,
            },
            {
                "date": "2026-08-22",
                "steps": 7000,
            },
        ]


fake_repo = FakeDailyLogsRepository()


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
    )


def override_daily_logs_repo():
    return fake_repo


app.dependency_overrides[get_current_user] = override_current_user
app.dependency_overrides[
    get_daily_logs_repository
] = override_daily_logs_repo

client = TestClient(app)


def test_get_daily_log():
    response = client.get(
        "/daily-logs/2026-08-22"
    )

    assert response.status_code == 200
    assert response.json()["item"]["steps"] == 7000
    assert fake_repo.last_get == (
        "authenticated-user",
        "2026-08-22",
    )


def test_update_daily_log_steps():
    response = client.patch(
        "/daily-logs/2026-08-22",
        json={"steps": 9000},
    )

    assert response.status_code == 200
    assert fake_repo.last_upsert == (
        "authenticated-user",
        "2026-08-22",
        {"steps": 9000},
    )


def test_update_daily_log_planning():
    response = client.patch(
        "/daily-logs/2026-08-22",
        json={
            "day_type": "Ufficio",
            "activity_plan": "Attiva",
        },
    )

    assert response.status_code == 200
    assert fake_repo.last_upsert == (
        "authenticated-user",
        "2026-08-22",
        {
            "day_type": "Ufficio",
            "activity_plan": "Attiva",
        },
    )


def test_empty_update_rejected():
    response = client.patch(
        "/daily-logs/2026-08-22",
        json={},
    )

    assert response.status_code == 400


def test_negative_steps_rejected():
    response = client.patch(
        "/daily-logs/2026-08-22",
        json={"steps": -1},
    )

    assert response.status_code == 422


def test_invalid_weight_rejected():
    response = client.patch(
        "/daily-logs/2026-08-22",
        json={"weight": 0},
    )

    assert response.status_code == 422


def test_get_daily_logs_range():
    response = client.get(
        "/daily-logs",
        params={
            "start_date": "2026-08-21",
            "end_date": "2026-08-22",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["count"] == 2
    assert fake_repo.last_range == (
        "authenticated-user",
        "2026-08-21",
        "2026-08-22",
    )


def test_invalid_range_rejected():
    response = client.get(
        "/daily-logs",
        params={
            "start_date": "2026-08-23",
            "end_date": "2026-08-22",
        },
    )

    assert response.status_code == 400
