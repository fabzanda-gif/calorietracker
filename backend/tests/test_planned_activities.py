import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.api.dependencies import CurrentUser
from backend.api.routers.activities import (
    PlannedActivityCreate,
    PlannedActivityUpdate,
    update_planned_activity,
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


# STEP A: planned activity edit guardrails


class FakePlannedEditRepository:
    def __init__(self, item):
        self.item = dict(item)
        self.last_update = None

    def get(self, activity_id, user_id):
        if (
            self.item.get("id") == activity_id
            and
            self.item.get("user_id") == user_id
        ):
            return dict(self.item)

        return None

    def update(
        self,
        activity_id,
        user_id,
        payload,
    ):
        self.last_update = (
            activity_id,
            user_id,
            dict(payload),
        )

        self.item.update(payload)
        return dict(self.item)


def planned_test_user():
    return CurrentUser(
        id="authenticated-user",
        access_token="fake-token",
    )


def running_planned_item(
    *,
    session_kind="easy",
    status="planned",
):
    return {
        "id": "planned-1",
        "user_id": "authenticated-user",
        "scheduled_date": "2026-09-10",
        "scheduled_time": "08:00:00",
        "title": "Corsa facile",
        "activity_type": "Corsa",
        "duration_minutes": 45,
        "distance_meters": 8000,
        "intensity": "low",
        "notes": None,
        "status": status,
        "training_plan_id": "running-plan-1",
        "training_week": 3,
        "session_kind": session_kind,
    }


def test_running_planned_session_edit_preserves_identity():
    repo = FakePlannedEditRepository(
        running_planned_item()
    )

    response = update_planned_activity(
        "planned-1",
        PlannedActivityUpdate(
            scheduled_date="2026-09-11",
            scheduled_time="09:30",
            title="Corsa facile spostata",
            duration_minutes=50,
            distance_meters=8500,
            notes="Partenza tranquilla",
        ),
        planned_test_user(),
        repo,
    )

    assert response["updated"] is True
    assert response["item"]["id"] == "planned-1"

    assert repo.last_update[0] == "planned-1"
    assert (
        repo.last_update[1]
        == "authenticated-user"
    )

    changes = repo.last_update[2]

    assert (
        changes["scheduled_date"]
        == "2026-09-11"
    )
    assert changes["distance_meters"] == 8500
    assert changes["duration_minutes"] == 50

    assert "training_plan_id" not in changes
    assert "training_week" not in changes
    assert "session_kind" not in changes


def test_running_plan_owned_fields_cannot_be_edited():
    repo = FakePlannedEditRepository(
        running_planned_item()
    )

    with pytest.raises(HTTPException) as exc:
        update_planned_activity(
            "planned-1",
            PlannedActivityUpdate(
                activity_type="Bici",
            ),
            planned_test_user(),
            repo,
        )

    assert exc.value.status_code == 409
    assert repo.last_update is None


def test_running_race_date_and_distance_are_protected():
    repo = FakePlannedEditRepository(
        running_planned_item(
            session_kind="race",
        )
    )

    with pytest.raises(HTTPException) as exc:
        update_planned_activity(
            "planned-1",
            PlannedActivityUpdate(
                scheduled_date="2026-09-12",
                distance_meters=10000,
            ),
            planned_test_user(),
            repo,
        )

    assert exc.value.status_code == 409
    assert repo.last_update is None


def test_completed_planned_activity_cannot_be_rewritten():
    repo = FakePlannedEditRepository(
        running_planned_item(
            status="completed",
        )
    )

    with pytest.raises(HTTPException) as exc:
        update_planned_activity(
            "planned-1",
            PlannedActivityUpdate(
                title="Titolo modificato",
            ),
            planned_test_user(),
            repo,
        )

    assert exc.value.status_code == 409
    assert repo.last_update is None
