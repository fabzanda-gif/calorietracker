import pytest
from pydantic import ValidationError

from backend.api.routers.activities import (
    PlannedActivityCreate,
    PlannedActivityUpdate,
)


def test_planned_activity_defaults():
    item = PlannedActivityCreate(
        scheduled_date="2026-09-10",
        title="Corsa facile",
        activity_type="Corsa",
    )

    assert item.intensity == "moderate"
    assert item.duration_minutes is None


def test_planned_activity_accepts_running_target():
    item = PlannedActivityCreate(
        scheduled_date="2026-09-10",
        scheduled_time="08:00",
        title="Lungo 12 km",
        activity_type="Corsa",
        duration_minutes=75,
        distance_meters=12000,
        intensity="low",
    )

    assert item.distance_meters == 12000
    assert item.duration_minutes == 75


def test_invalid_intensity_is_rejected():
    with pytest.raises(ValidationError):
        PlannedActivityCreate(
            scheduled_date="2026-09-10",
            title="Test",
            activity_type="Corsa",
            intensity="impossible",
        )


def test_planned_status_validation():
    with pytest.raises(ValidationError):
        PlannedActivityUpdate(
            status="maybe",
        )
