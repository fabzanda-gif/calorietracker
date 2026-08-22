from fastapi.testclient import TestClient

from backend.api.dependencies import CurrentUser, get_current_user
from backend.api.main import app
from backend.api.routers.activities import get_activities_repository


class FakeActivitiesRepository:
    def __init__(self):
        self.last_create = None
        self.last_update = None
        self.last_delete = None

    def list_for_date(self, user_id, log_date):
        assert user_id == "authenticated-user"
        assert str(log_date) == "2026-08-22"

        return [
            {
                "id": "activity-1",
                "activity_name": "Padel",
                "burned_calories": 500,
            }
        ]

    def create(self, payload):
        self.last_create = payload
        return {
            "id": "activity-2",
            **payload,
        }

    def update(self, activity_id, user_id, payload):
        self.last_update = (
            activity_id,
            user_id,
            payload,
        )

        return {
            "id": activity_id,
            **payload,
        }

    def delete(self, activity_id, user_id):
        self.last_delete = (
            activity_id,
            user_id,
        )
        return True


fake_repo = FakeActivitiesRepository()


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
    )


def override_activities_repo():
    return fake_repo


app.dependency_overrides[get_current_user] = override_current_user
app.dependency_overrides[
    get_activities_repository
] = override_activities_repo

client = TestClient(app)


def test_list_activities():
    response = client.get(
        "/activities/2026-08-22"
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["count"] == 1
    assert payload["items"][0]["activity_name"] == "Padel"


def test_create_activity_uses_authenticated_user():
    response = client.post(
        "/activities",
        json={
            "date": "2026-08-22",
            "activity_name": "Bici",
            "burned_calories": 320,
        },
    )

    assert response.status_code == 201
    assert fake_repo.last_create["user_id"] == "authenticated-user"
    assert fake_repo.last_create["date"] == "2026-08-22"


def test_update_activity_is_user_scoped():
    response = client.patch(
        "/activities/activity-1",
        json={
            "burned_calories": 550
        },
    )

    assert response.status_code == 200
    assert fake_repo.last_update == (
        "activity-1",
        "authenticated-user",
        {"burned_calories": 550},
    )


def test_update_activity_rejects_empty_body():
    response = client.patch(
        "/activities/activity-1",
        json={},
    )

    assert response.status_code == 400


def test_delete_activity_is_user_scoped():
    response = client.delete(
        "/activities/activity-1"
    )

    assert response.status_code == 200
    assert fake_repo.last_delete == (
        "activity-1",
        "authenticated-user",
    )
