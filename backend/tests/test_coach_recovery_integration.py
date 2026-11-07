"""In-memory integration checks for Coach preview -> approval -> refreshed calendar.

The fake repositories exercise the actual Coach context and endpoint functions,
without requiring a live database or changing a user's workout records.
"""
from copy import deepcopy
from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from backend.api.dependencies import CurrentUser
from backend.api.routers.coach import (
    CoachRecoveryApplyRequest,
    _coach_context,
    apply_skipped_session_recovery,
)


class PlannedRepo:
    def __init__(self, sessions):
        self.sessions = {item["id"]: deepcopy(item) for item in sessions}
        self.writes = 0

    def get(self, activity_id, user_id):
        item = self.sessions.get(activity_id)
        return deepcopy(item) if item else None

    def list_range(self, user_id, start, end):
        return [
            deepcopy(item) for item in self.sessions.values()
            if str(start) <= item["scheduled_date"] <= str(end)
        ]

    def reschedule_skipped(self, *, activity_id, user_id, original_date, new_date):
        item = self.sessions.get(activity_id)
        if not item or item["status"] != "skipped" or item["scheduled_date"] != original_date:
            return None
        item.update({"scheduled_date": new_date, "status": "planned"})
        self.writes += 1
        return deepcopy(item)


class WorkoutsRepo:
    def __init__(self, workouts):
        self.workouts = {item["id"]: deepcopy(item) for item in workouts}
        self.writes = 0

    def get(self, user_id, workout_id):
        item = self.workouts.get(workout_id)
        return deepcopy(item) if item else None

    def list_date_range(self, user_id, start, end):
        return [
            deepcopy(item) for item in self.workouts.values()
            if str(start) <= item["scheduled_date"] <= str(end)
        ]

    def reschedule_skipped(self, *, workout_id, user_id, original_date, new_date):
        item = self.workouts.get(workout_id)
        if not item or item["status"] != "skipped" or item["scheduled_date"] != original_date:
            return None
        item.update({"scheduled_date": new_date, "status": "planned"})
        self.writes += 1
        return deepcopy(item)


class PlansRepo:
    def __init__(self, status="completed"):
        self.status = status
        self.writes = 0

    def get(self, plan_id, user_id):
        return {"id": plan_id, "status": self.status}

    def reopen_completed(self, *, plan_id, user_id):
        if self.status != "completed":
            return None
        self.status = "active"
        self.writes += 1
        return {"id": plan_id, "status": self.status}


class ActivitiesRepo:
    def __init__(self, activities=None):
        self.activities = activities or []

    def list_date_range(self, user_id, start, end):
        return [
            deepcopy(item) for item in self.activities
            if str(start) <= item["date"] <= str(end)
        ]


class WorkoutLogsRepo:
    def __init__(self, items=None):
        self.items = items or []

    def list_date_range(self, user_id, start, end):
        return [
            item for item in self.items
            if str(start) <= item["performed_date"] <= str(end)
        ]


class ExercisesRepo:
    def list_for_workout(self, user_id, workout_id):
        return []


class SetLogsRepo:
    def list_for_workout_log(self, user_id, workout_log_id):
        return []


def fixtures(running=None, strength=None, activities=None, logs=None, plan_status="completed"):
    return {
        "current_user": CurrentUser(id="user-1", access_token="token"),
        "planned_repo": PlannedRepo(running or []),
        "workouts_repo": WorkoutsRepo(strength or []),
        "plans_repo": PlansRepo(plan_status),
        "activities_repo": ActivitiesRepo(activities),
        "workout_logs_repo": WorkoutLogsRepo(logs),
        "exercises_repo": ExercisesRepo(),
        "set_logs_repo": SetLogsRepo(),
    }


def preview(args, today):
    return _coach_context(
        user_id="user-1",
        as_of=today,
        activities_repo=args["activities_repo"],
        planned_repo=args["planned_repo"],
        workouts_repo=args["workouts_repo"],
        exercises_repo=args["exercises_repo"],
        workout_logs_repo=args["workout_logs_repo"],
        set_logs_repo=args["set_logs_repo"],
    )["recovery_alerts"]


def approve(args, item):
    return apply_skipped_session_recovery(
        kind=item["kind"],
        session_id=item["session_id"],
        request=CoachRecoveryApplyRequest(
            original_date=date.fromisoformat(item["scheduled_date"]),
            suggested_date=date.fromisoformat(item["suggested_date"]),
        ),
        **args,
    )


def test_skipped_run_preview_approval_and_refresh():
    today = date.today()
    previous = (today - timedelta(days=1)).isoformat()
    args = fixtures(
        running=[{
            "id": "run-1",
            "status": "skipped",
            "activity_type": "running",
            "session_kind": "easy",
            "intensity": "low",
            "scheduled_date": previous,
            "title": "Easy run",
        }],
        activities=[{
            "id": "activity-1",
            "date": today.isoformat(),
            "activity_type": "running",
            "activity_name": "Hard run",
            "duration_seconds": 75 * 60,
            "distance_meters": 12000,
        }],
    )
    item = preview(args, today)[0]
    assert item["suggested_date"] == (today + timedelta(days=3)).isoformat()
    assert args["planned_repo"].writes == 0  # Preview is read-only.
    result = approve(args, item)
    assert result["applied"] is True
    assert result["item"]["status"] == "planned"
    assert result["item"]["scheduled_date"] == item["suggested_date"]
    assert args["planned_repo"].writes == 1
    assert preview(args, today) == []  # No duplicate recovery offer.


def test_skipped_final_strength_workout_reopens_plan():
    today = date.today()
    args = fixtures(strength=[{
        "id": "gym-1",
        "status": "skipped",
        "scheduled_date": (today - timedelta(days=1)).isoformat(),
        "strength_plan_id": "plan-1",
        "focus": "upper",
        "title": "Upper A",
    }])
    item = preview(args, today)[0]
    assert item["suggested_date"] is not None
    assert args["plans_repo"].writes == 0
    result = approve(args, item)
    assert result["applied"] is True
    assert result["plan"]["status"] == "active"
    assert args["plans_repo"].writes == 1
    assert args["workouts_repo"].writes == 1
    assert preview(args, today) == []


def test_calendar_changed_after_preview_rejects_recovery_without_writes():
    today = date.today()
    args = fixtures(running=[{
        "id": "run-1",
        "status": "skipped",
        "activity_type": "running",
        "session_kind": "easy",
        "intensity": "low",
        "scheduled_date": (today - timedelta(days=1)).isoformat(),
    }])
    item = preview(args, today)[0]
    assert item["suggested_date"]
    # Another workout is added on the proposed day after preview.
    args["workouts_repo"].workouts["gym-new"] = {
        "id": "gym-new",
        "status": "planned",
        "scheduled_date": item["suggested_date"],
        "focus": "lower",
    }
    with pytest.raises(HTTPException) as exc:
        approve(args, item)
    assert exc.value.status_code == 409
    assert args["planned_repo"].writes == 0
    assert args["planned_repo"].sessions["run-1"]["status"] == "skipped"
