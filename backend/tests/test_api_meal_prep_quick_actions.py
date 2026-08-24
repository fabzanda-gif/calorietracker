import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_meal_prep_repository,
    get_recipes_repository,
)
from backend.api.main import app


class FakeRecipesRepository:
    pass


class FakeMealPrepRepository:
    def __init__(self):
        self.item = None

    def reset(self):
        self.item = {
            "id": "batch-1",
            "user_id": "authenticated-user",
            "name": "Chili",
            "portions_prepared": 6,
            "portions_remaining": 4,
            "status": "available",
        }

    def get_by_id(self, batch_id, user_id):
        if (
            self.item
            and batch_id == self.item["id"]
            and user_id == self.item["user_id"]
        ):
            return self.item
        return None

    def update(self, batch_id, user_id, payload):
        self.item.update(payload)
        return self.item


repo = FakeMealPrepRepository()


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
    )


@pytest.fixture(autouse=True)
def overrides():
    repo.reset()
    app.dependency_overrides[get_current_user] = (
        override_current_user
    )
    app.dependency_overrides[get_meal_prep_repository] = (
        lambda: repo
    )
    app.dependency_overrides[get_recipes_repository] = (
        lambda: FakeRecipesRepository()
    )
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_remaining_route_is_registered():
    assert (
        "/meal-prep/{batch_id}/remaining"
        in app.openapi()["paths"]
    )


def test_quick_remaining_update():
    response = client.patch(
        "/meal-prep/batch-1/remaining",
        json={"portions_remaining": 2},
    )

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["portions_remaining"] == 2
    assert item["status"] == "available"


def test_quick_zero_remaining_marks_finished():
    response = client.patch(
        "/meal-prep/batch-1/remaining",
        json={"portions_remaining": 0},
    )

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["portions_remaining"] == 0
    assert item["status"] == "finished"
