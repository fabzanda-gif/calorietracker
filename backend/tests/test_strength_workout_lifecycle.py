import pytest
from fastapi import HTTPException

from backend.api.dependencies import CurrentUser
from backend.api.routers.strength import (
    cancel_strength_plan,
    skip_strength_workout,
)


def user():
    return CurrentUser(
        id="user-1",
        access_token="token",
    )


class PlansRepo:
    def __init__(
        self,
        status="active",
    ):
        self.status = status
        self.status_updates = []

    def get(self, plan_id, user_id):
        return {
            "id": plan_id,
            "user_id": user_id,
            "status": self.status,
        }

    def update_status(
        self,
        *,
        plan_id,
        user_id,
        status,
    ):
        self.status = status
        self.status_updates.append(
            (plan_id, status)
        )

        return {
            "id": plan_id,
            "status": status,
        }


class WorkoutsRepo:
    def __init__(
        self,
        *,
        status="planned",
        all_done=False,
    ):
        self.status = status
        self.all_done = all_done

    def get(
        self,
        user_id,
        workout_id,
    ):
        return {
            "id": workout_id,
            "strength_plan_id": "plan-1",
            "status": self.status,
        }

    def update_status(
        self,
        *,
        user_id,
        workout_id,
        status,
    ):
        self.status = status

        return {
            "id": workout_id,
            "strength_plan_id": "plan-1",
            "status": status,
        }

    def list_for_plan(
        self,
        user_id,
        plan_id,
    ):
        first = {
            "id": "workout-1",
            "status": self.status,
        }

        if self.all_done:
            return [first]

        return [
            first,
            {
                "id": "workout-2",
                "status": "planned",
            },
        ]


class WorkoutLogsRepo:
    def __init__(
        self,
        existing=False,
    ):
        self.existing = existing

    def get_for_workout(
        self,
        user_id,
        workout_id,
    ):
        if self.existing:
            return {
                "id": "log-1",
            }

        return None


def test_skip_marks_workout_skipped():
    plans = PlansRepo()
    workouts = WorkoutsRepo()

    result = skip_strength_workout(
        workout_id="workout-1",
        current_user=user(),
        workouts_repo=workouts,
        plans_repo=plans,
        workout_logs_repo=(
            WorkoutLogsRepo()
        ),
    )

    assert result["skipped"] is True

    assert (
        result["workout"]["status"]
        == "skipped"
    )

    assert plans.status_updates == []


def test_last_skipped_workout_completes_plan():
    plans = PlansRepo()

    workouts = WorkoutsRepo(
        all_done=True,
    )

    result = skip_strength_workout(
        workout_id="workout-1",
        current_user=user(),
        workouts_repo=workouts,
        plans_repo=plans,
        workout_logs_repo=(
            WorkoutLogsRepo()
        ),
    )

    assert (
        result["plan"]["status"]
        == "completed"
    )

    assert plans.status_updates == [
        ("plan-1", "completed")
    ]


def test_logged_workout_cannot_be_skipped():
    with pytest.raises(
        HTTPException
    ) as exc:
        skip_strength_workout(
            workout_id="workout-1",
            current_user=user(),
            workouts_repo=WorkoutsRepo(),
            plans_repo=PlansRepo(),
            workout_logs_repo=(
                WorkoutLogsRepo(
                    existing=True,
                )
            ),
        )

    assert exc.value.status_code == 409


def test_non_planned_workout_cannot_be_skipped():
    with pytest.raises(
        HTTPException
    ) as exc:
        skip_strength_workout(
            workout_id="workout-1",
            current_user=user(),
            workouts_repo=(
                WorkoutsRepo(
                    status="completed",
                )
            ),
            plans_repo=PlansRepo(),
            workout_logs_repo=(
                WorkoutLogsRepo()
            ),
        )

    assert exc.value.status_code == 409


def test_cancel_active_plan():
    plans = PlansRepo()

    result = cancel_strength_plan(
        plan_id="plan-1",
        current_user=user(),
        plans_repo=plans,
    )

    assert result["cancelled"] is True

    assert (
        result["plan"]["status"]
        == "cancelled"
    )


def test_non_active_plan_cannot_be_cancelled():
    with pytest.raises(
        HTTPException
    ) as exc:
        cancel_strength_plan(
            plan_id="plan-1",
            current_user=user(),
            plans_repo=PlansRepo(
                status="completed",
            ),
        )

    assert exc.value.status_code == 409
