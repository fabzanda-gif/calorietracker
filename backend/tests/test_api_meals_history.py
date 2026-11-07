from backend.api.dependencies import CurrentUser
from backend.api.routers.meals import get_meal_history, router as meals_router


def test_meals_history_routes_are_registered():
    paths = {
        route.path
        for route in meals_router.routes
    }

    assert "/meals/history" in paths
    assert "/meals/range" in paths
    assert "/meals/by-type/{meal_type}" in paths


def test_meals_history_unpacks_repository_compatibility_result():
    class FakeRepository:
        def list_history_compatible(self, user_id):
            assert user_id == "user-1"
            return ([{"id": "meal-1", "name": "Pasta"}], True)

    result = get_meal_history(
        current_user=CurrentUser(
            id="user-1",
            access_token="token",
            metadata={},
        ),
        repo=FakeRepository(),
    )

    assert result == {
        "count": 1,
        "items": [{"id": "meal-1", "name": "Pasta"}],
    }
