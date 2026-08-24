import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_ingredients_repository,
)
from backend.api.main import app


class FakeIngredientsRepository:
    def __init__(self):
        self.items = {
            "ingredient-1": {
                "id": "ingredient-1",
                "user_id": "authenticated-user",
                "name": "Petto di pollo",
                "normalized_name": "petto di pollo",
                "calories_per_100g": 165,
                "protein_per_100g": 31,
                "carbs_per_100g": 0,
                "fat_per_100g": 3.6,
                "default_unit": "g",
            }
        }

        self.last_create = None
        self.last_update = None
        self.last_delete = None

    def list_for_user(self, user_id):
        return [
            dict(item)
            for item in self.items.values()
            if item["user_id"] == user_id
        ]

    def get_by_id(
        self,
        ingredient_id,
        user_id,
    ):
        item = self.items.get(
            ingredient_id
        )

        if (
            item is None
            or item["user_id"] != user_id
        ):
            return None

        return dict(item)

    def create(self, payload):
        self.last_create = dict(payload)

        item = {
            "id": "ingredient-new",
            **payload,
        }

        self.items[item["id"]] = item
        return dict(item)

    def update(
        self,
        ingredient_id,
        user_id,
        payload,
    ):
        self.last_update = (
            ingredient_id,
            user_id,
            dict(payload),
        )

        item = self.items[
            ingredient_id
        ]
        item.update(payload)

        return dict(item)

    def delete(
        self,
        ingredient_id,
        user_id,
    ):
        self.last_delete = (
            ingredient_id,
            user_id,
        )

        self.items.pop(
            ingredient_id,
            None,
        )

        return True


fake_repo = FakeIngredientsRepository()


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
    )


@pytest.fixture(autouse=True)
def api_overrides():
    app.dependency_overrides[
        get_current_user
    ] = override_current_user

    app.dependency_overrides[
        get_ingredients_repository
    ] = lambda: fake_repo

    yield

    app.dependency_overrides.clear()


client = TestClient(app)


def test_list_ingredients():
    response = client.get(
        "/ingredients"
    )

    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_get_ingredient():
    response = client.get(
        "/ingredients/ingredient-1"
    )

    assert response.status_code == 200

    assert (
        response.json()["item"]["name"]
        == "Petto di pollo"
    )


def test_missing_ingredient_is_404():
    response = client.get(
        "/ingredients/missing"
    )

    assert response.status_code == 404


def test_create_ingredient_uses_authenticated_user():
    response = client.post(
        "/ingredients",
        json={
            "name": "  Riso Basmati  ",
            "calories_per_100g": 350,
            "protein_per_100g": 7,
            "carbs_per_100g": 78,
            "fat_per_100g": 1,
        },
    )

    assert response.status_code == 201

    assert (
        fake_repo.last_create[
            "user_id"
        ]
        == "authenticated-user"
    )

    assert (
        fake_repo.last_create[
            "normalized_name"
        ]
        == "riso basmati"
    )

    assert (
        fake_repo.last_create["name"]
        == "Riso Basmati"
    )


def test_update_name_recomputes_normalized_name():
    response = client.patch(
        "/ingredients/ingredient-1",
        json={
            "name": "  Pollo Arrosto  ",
        },
    )

    assert response.status_code == 200

    payload = fake_repo.last_update[2]

    assert payload["name"] == "Pollo Arrosto"
    assert (
        payload["normalized_name"]
        == "pollo arrosto"
    )


def test_empty_update_is_rejected():
    response = client.patch(
        "/ingredients/ingredient-1",
        json={},
    )

    assert response.status_code == 400


def test_delete_ingredient():
    response = client.delete(
        "/ingredients/ingredient-1"
    )

    assert response.status_code == 200

    assert fake_repo.last_delete == (
        "ingredient-1",
        "authenticated-user",
    )
