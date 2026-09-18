from datetime import date

from backend.api.routers.weekly_schedule import (
    DAY_NAMES,
    _default_schedule,
    _monday,
    _resolve_schedule,
)


def test_monday_normalizes_week_start():
    assert _monday(date(2026, 8, 31)) == date(2026, 8, 31)
    assert _monday(date(2026, 9, 2)) == date(2026, 8, 31)


def test_default_schedule_uses_profile_metadata():
    metadata = {
        "weekly_schedule": {
            "tuesday": "office",
            "thursday": "office",
            "saturday": "free",
            "sunday": "free",
        }
    }

    result = _default_schedule(metadata)

    assert result["monday"] == "home"
    assert result["tuesday"] == "office"
    assert result["thursday"] == "office"
    assert result["saturday"] == "free"
    assert result["sunday"] == "free"


def test_default_schedule_falls_back_to_home():
    result = _default_schedule({})

    assert set(result) == set(DAY_NAMES)
    assert all(value == "home" for value in result.values())


def test_override_replaces_default_for_current_week():
    current_user = type(
        "User",
        (),
        {
            "metadata": {
                "weekly_schedule": {
                    "tuesday": "office",
                    "thursday": "office",
                }
            }
        },
    )()

    rows = [
        {
            "day_of_week": 2,
            "context": "home",
        },
        {
            "day_of_week": 6,
            "context": "free",
        },
    ]

    result = _resolve_schedule(
        current_user=current_user,
        rows=rows,
        week_start=date(2026, 8, 31),
    )

    assert result["days"]["monday"] == "home"
    assert result["days"]["tuesday"] == "home"
    assert result["days"]["thursday"] == "office"
    assert result["days"]["saturday"] == "free"

    assert result["overrides"] == {
        "tuesday": "home",
        "saturday": "free",
    }
