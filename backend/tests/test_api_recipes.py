from fastapi.testclient import TestClient

from backend.api.dependencies import CurrentUser, get_current_user
from backend.api.main import app
from backend.api.routers.recipes import get_recipes_repository


class FakeRecipesRepository:
    def __init__(self):
        self.last_create = None
        self.last_update = None
        self.last_share = None
        self.last_delete = None
        self.last_exclude = "not-called"

    def list_personal(self, user_id):
        assert user_id == "authenticated-user"
        return [
            {
                "id": "recipe-1",
                "name": "Pasta",
                "is_shared": False,
            }
        ]

    def list_available(self, user_id):
        assert user_id == "authenticated-user"
        return [
            {"id": "recipe-1", "name": "Pasta"},
            {"id": "recipe-2", "name": "Shared Rice"},
        ]

    def list_shared(self, exclude_user_id=None):
        self.last_exclude = exclude_user_id
        return [
            {
                "id": "recipe-2",
                "name": "Shared Rice",
                "is_shared": True,
            }
        ]

    def get_personal_by_id(self, recipe_id, user_id):
        assert user_id == "authenticated-user"
        if recipe_id == "missing":
            return None
        return {
            "id": recipe_id,
            "name": "Pasta",
        }

    def create(self, payload):
        self.last_create = payload
        return {
            "id": "recipe-new",
            **payload,
        }

    def update(self, recipe_id, user_id, payload):
        self.last_update = (
            recipe_id,
            user_id,
            payload,
        )
        return {
            "id": recipe_id,
            **payload,
        }

    def set_shared(self, recipe_id, user_id, is_shared):
        self.last_share = (
            recipe_id,
            user_id,
            is_shared,
        )
        return {
            "id": recipe_id,
            "is_shared": is_shared,
        }

    def delete(self, recipe_id, user_id):
        self.last_delete = (
            recipe_id,
            user_id,
        )
        return True


fake_repo = FakeRecipesRepository()


def override_current_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
    )


def override_recipes_repo():
    return fake_repo


app.dependency_overrides[get_current_user] = override_current_user
app.dependency_overrides[
    get_recipes_repository
] = override_recipes_repo

client = TestClient(app)


def test_list_personal_recipes():
    response = client.get("/recipes")

    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_list_available_recipes():
    response = client.get("/recipes/available")

    assert response.status_code == 200
    assert response.json()["count"] == 2


def test_list_shared_recipes():
    response = client.get("/recipes/shared")

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert fake_repo.last_exclude is None


def test_list_shared_recipes_can_exclude_mine():
    response = client.get(
        "/recipes/shared",
        params={"exclude_mine": "true"},
    )

    assert response.status_code == 200
    assert fake_repo.last_exclude == "authenticated-user"


def test_get_personal_recipe():
    response = client.get("/recipes/recipe-1")

    assert response.status_code == 200
    assert response.json()["item"]["name"] == "Pasta"


def test_missing_personal_recipe_returns_404():
    response = client.get("/recipes/missing")

    assert response.status_code == 404


def test_create_recipe_uses_authenticated_user():
    response = client.post(
        "/recipes",
        json={
            "name": "Rice Bowl",
            "meal_type": "Cena",
            "calories": 500,
            "protein": 25,
            "carbs": 70,
            "fat": 12,
            "ingredients_json": [
                {
                    "name": "Rice",
                    "quantity": 100,
                }
            ],
        },
    )

    assert response.status_code == 201
    assert fake_repo.last_create["user_id"] == "authenticated-user"
    assert fake_repo.last_create["name"] == "Rice Bowl"


def test_update_recipe_is_user_scoped():
    response = client.patch(
        "/recipes/recipe-1",
        json={
            "calories": 550,
            "protein": 30,
        },
    )

    assert response.status_code == 200
    assert fake_repo.last_update == (
        "recipe-1",
        "authenticated-user",
        {
            "calories": 550,
            "protein": 30,
        },
    )


def test_empty_recipe_update_rejected():
    response = client.patch(
        "/recipes/recipe-1",
        json={},
    )

    assert response.status_code == 400


def test_update_recipe_sharing():
    response = client.patch(
        "/recipes/recipe-1/sharing",
        json={"is_shared": True},
    )

    assert response.status_code == 200
    assert fake_repo.last_share == (
        "recipe-1",
        "authenticated-user",
        True,
    )


def test_delete_recipe_is_user_scoped():
    response = client.delete(
        "/recipes/recipe-1"
    )

    assert response.status_code == 200
    assert fake_repo.last_delete == (
        "recipe-1",
        "authenticated-user",
    )
