from fastapi.testclient import TestClient

from backend.api.dependencies import CurrentUser, get_current_user
from backend.api.main import app
from backend.api.routers.weight import get_weight_repository


class FakeWeightRepository:
    def __init__(self):
        self.last_save = None
        self.last_update = None
        self.last_move = None
        self.last_delete = None

    def history(self, user_id):
        assert user_id == "authenticated-user"
        return [
            {
                "id": "row-1",
                "date": "2026-08-20",
                "weight": 80.0,
            },
            {
                "id": "row-2",
                "date": "2026-08-22",
                "weight": 79.5,
            },
        ]

    def latest(self, user_id):
        assert user_id == "authenticated-user"
        return {
            "id": "row-2",
            "date": "2026-08-22",
            "weight": 79.5,
        }

    def save(self, user_id, log_date, weight):
        self.last_save = (
            user_id,
            str(log_date),
            weight,
        )
        return {
            "id": "row-3",
            "date": str(log_date),
            "weight": weight,
        }

    def update_weight(self, row_id, user_id, weight):
        self.last_update = (
            row_id,
            user_id,
            weight,
        )
        return {
            "id": row_id,
            "weight": weight,
        }

    def move_weight(
        self,
        row_id,
        user_id,
        new_date,
        weight,
    ):
        self.last_move = (
            row_id,
            user_id,
            str(new_date),
            weight,
        )
        return {
            "id": row_id,
            "date": str(new_date),
            "weight": weight,
        }

    def delete_weight(self, row_id, user_id):
        self.last_delete = (
            row_id,
            user_id,
        )
        return {
            "id": row_id,
            "weight": None,
        }


fake_repo = FakeWeightRepository()


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
    )


def override_weight_repo():
    return fake_repo


app.dependency_overrides[get_current_user] = override_current_user
app.dependency_overrides[
    get_weight_repository
] = override_weight_repo

client = TestClient(app)


def test_weight_history():
    response = client.get("/weight")

    assert response.status_code == 200
    payload = response.json()

    assert payload["count"] == 2
    assert payload["items"][-1]["weight"] == 79.5


def test_latest_weight():
    response = client.get("/weight/latest")

    assert response.status_code == 200
    assert response.json()["item"]["weight"] == 79.5


def test_create_weight_uses_authenticated_user():
    response = client.post(
        "/weight",
        json={
            "date": "2026-08-22",
            "weight": 79.4,
        },
    )

    assert response.status_code == 201
    assert fake_repo.last_save == (
        "authenticated-user",
        "2026-08-22",
        79.4,
    )


def test_update_weight_value():
    response = client.patch(
        "/weight/row-2",
        json={"weight": 79.3},
    )

    assert response.status_code == 200
    assert fake_repo.last_update == (
        "row-2",
        "authenticated-user",
        79.3,
    )


def test_move_weight_date():
    response = client.patch(
        "/weight/row-2",
        json={
            "date": "2026-08-21",
            "weight": 79.3,
        },
    )

    assert response.status_code == 200
    assert fake_repo.last_move == (
        "row-2",
        "authenticated-user",
        "2026-08-21",
        79.3,
    )


def test_move_weight_requires_weight():
    response = client.patch(
        "/weight/row-2",
        json={"date": "2026-08-21"},
    )

    assert response.status_code == 400


def test_empty_update_rejected():
    response = client.patch(
        "/weight/row-2",
        json={},
    )

    assert response.status_code == 400


def test_delete_weight_is_user_scoped():
    response = client.delete(
        "/weight/row-2"
    )

    assert response.status_code == 200
    assert fake_repo.last_delete == (
        "row-2",
        "authenticated-user",
    )
