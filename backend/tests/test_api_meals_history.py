from backend.api.routers.meals import router as meals_router


def test_meals_history_routes_are_registered():
    paths = {
        route.path
        for route in meals_router.routes
    }

    assert "/meals/history" in paths
    assert "/meals/range" in paths
    assert "/meals/by-type/{meal_type}" in paths
