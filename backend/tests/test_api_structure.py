from backend.api.main import app


def test_expected_api_paths_are_registered():
    paths = set(app.openapi()["paths"].keys())

    expected = {
        "/health",
        "/meals/{meal_date}",
        "/meals",
        "/meals/{meal_id}",
        "/activities/{activity_date}",
        "/activities",
        "/activities/{activity_id}",
        "/weight",
        "/weight/latest",
        "/weight/{row_id}",
        "/daily-logs/{log_date}",
        "/daily-logs",
        "/recipes",
        "/recipes/available",
        "/recipes/shared",
        "/recipes/{recipe_id}",
        "/recipes/{recipe_id}/sharing",
    }

    missing = expected - paths
    assert not missing, f"Missing API paths: {sorted(missing)}"


def test_all_data_routes_have_bearer_security():
    schema = app.openapi()

    public_paths = {"/health"}

    for path, operations in schema["paths"].items():
        if path in public_paths:
            continue

        for method, operation in operations.items():
            if method.lower() not in {
                "get",
                "post",
                "patch",
                "put",
                "delete",
            }:
                continue

            security = operation.get("security")
            assert security, (
                f"{method.upper()} {path} is missing authentication security"
            )


def test_api_metadata():
    assert app.title == "SanoSync API"
    assert app.version == "0.3.0"
