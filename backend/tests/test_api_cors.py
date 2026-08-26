from fastapi.testclient import TestClient

from backend.api.main import app


client = TestClient(app)


def test_localhost_origin_is_allowed_by_default():
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "http://localhost:3000"
    )
