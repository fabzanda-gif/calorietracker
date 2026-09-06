from datetime import date

import pytest
from fastapi import HTTPException

from backend.api.dependencies import CurrentUser
from backend.api.routers.activities import (
    RunningTrainingPlanCreate,
    create_running_training_plan,
)


class FakePlansRepository:
    def __init__(self, active=True):
        self.created = []
        self.deleted = []

        self.existing = (
            [
                {
                    "id": "old-plan",
                    "sport": "running",
                    "status": "active",
                }
            ]
            if active
            else []
        )

    def list_for_user(self, user_id):
        return list(self.existing)

    def create(self, payload):
        item = {
            **payload,
            "id": "new-plan",
        }
        self.created.append(item)
        return item

    def delete(self, plan_id, user_id):
        self.deleted.append(
            (plan_id, user_id)
        )
        return True


class FakePlannedRepository:
    def __init__(self):
        self.created = []

    def create_many(self, payloads):
        self.created = [
            {
                **item,
                "id": f"session-{index}",
            }
            for index, item in enumerate(
                payloads,
                start=1,
            )
        ]
        return self.created


def request(**overrides):
    values = {
        "start_date": date(2026, 9, 7),
        "target_date": date(2027, 3, 7),
        "current_distance_meters": 5000,
        "current_pace_seconds_per_km": 360,
        "target_distance_meters": 21100,
        "target_pace_seconds_per_km": 300,
        "sessions_per_week": 3,
        "long_run_weekday": 6,
        "replace_active": False,
    }
    values.update(overrides)

    return RunningTrainingPlanCreate(
        **values
    )


def user():
    return CurrentUser(
        id="user-1",
        access_token="token",
    )


def test_second_active_plan_is_rejected():
    plans = FakePlansRepository(
        active=True
    )
    sessions = FakePlannedRepository()

    with pytest.raises(
        HTTPException
    ) as exc:
        create_running_training_plan(
            request=request(),
            current_user=user(),
            plans_repo=plans,
            planned_repo=sessions,
        )

    assert exc.value.status_code == 409
    assert plans.created == []
    assert plans.deleted == []


def test_replace_active_plan_creates_new_then_deletes_old():
    plans = FakePlansRepository(
        active=True
    )
    sessions = FakePlannedRepository()

    response = create_running_training_plan(
        request=request(
            replace_active=True
        ),
        current_user=user(),
        plans_repo=plans,
        planned_repo=sessions,
    )

    assert response["created"] is True
    assert response["plan"]["id"] == (
        "new-plan"
    )

    assert len(sessions.created) > 0

    assert plans.deleted == [
        ("old-plan", "user-1")
    ]

    assert response[
        "replaced_plan_ids"
    ] == ["old-plan"]


def test_first_plan_does_not_require_replace():
    plans = FakePlansRepository(
        active=False
    )
    sessions = FakePlannedRepository()

    response = create_running_training_plan(
        request=request(),
        current_user=user(),
        plans_repo=plans,
        planned_repo=sessions,
    )

    assert response["created"] is True
    assert plans.deleted == []
