from backend.api.core_main import app


def test_core_api_does_not_mount_heavy_routes():
    schema = app.openapi()
    paths = set(schema["paths"])

    assert "/profile" in paths
    assert "/pantry" in paths
    assert "/weight" in paths
    assert "/days/{day_date}/home-core" in paths

    assert "/meals/conversational/preview" not in paths
    assert "/meals/photo/preview" not in paths
    assert "/activities" not in paths
    assert "/integrations/oura/status" not in paths
    assert "/integrations/google-calendar/status" not in paths


def test_core_api_health_is_available():
    schema = app.openapi()
    assert "/health" in schema["paths"]
    assert "/health/live" in schema["paths"]
    assert "/health/ready" in schema["paths"]
