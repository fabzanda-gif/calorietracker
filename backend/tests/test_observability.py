import json

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.observability import new_request_id


client = TestClient(app)


def test_health_response_preserves_request_id(capsys):
    response = client.get(
        "/health",
        headers={"X-Request-ID": "test-request-123"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-123"

    events = []
    for line in capsys.readouterr().out.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    request_event = next(
        event
        for event in events
        if event.get("event") == "api_request"
    )

    assert request_event == {
        "event": "api_request",
        "request_id": "test-request-123",
        "method": "GET",
        "path": "/health",
        "duration_ms": request_event["duration_ms"],
        "status_code": 200,
    }
    assert isinstance(request_event["duration_ms"], int)


def test_missing_or_oversized_request_id_is_replaced():
    generated = new_request_id()
    oversized = new_request_id("x" * 129)

    assert len(generated) == 32
    assert len(oversized) == 32
    assert oversized != "x" * 129
