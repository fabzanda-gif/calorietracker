from backend.services.activity_comment import (
    fallback_activity_comment,
)


def test_standard_activity_comment_fallback():
    message = fallback_activity_comment(
        {
            "activity_name": "Corsa",
            "duration_seconds": 4200,
            "distance_meters": 8500,
            "burned_calories": 620,
        },
        mode="standard",
    )

    assert "Corsa" in message
    assert "sessione" in message.lower()
    assert "divano" not in message.lower()


def test_zero_activity_comment_fallback():
    message = fallback_activity_comment(
        {
            "activity_name": "Corsa",
            "duration_seconds": 4200,
            "distance_meters": 8500,
            "burned_calories": 620,
        },
        mode="zero",
    )

    assert "Corsa" in message
    assert "divano" in message.lower()


def test_zero_activity_comment_does_not_require_metrics():
    message = fallback_activity_comment(
        {
            "activity_name": "Padel",
            "burned_calories": 0,
        },
        mode="zero",
    )

    assert "Padel" in message
    assert message
