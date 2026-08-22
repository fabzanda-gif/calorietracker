from backend.api.main import app


def test_meals_history_routes_are_registered():
    paths = {
        route.path
        for route in app.routes
        if getattr(route, "path", "").startswith("/meals")
    }

    assert "/meals/history" in paths
    assert "/meals/range" in paths
    assert "/meals/by-type/{meal_type}" in paths
