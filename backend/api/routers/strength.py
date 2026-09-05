from __future__ import annotations

from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_strength_plans_repository,
    get_strength_workout_exercises_repository,
    get_strength_workouts_repository,
)
from backend.repositories.base import RepositoryError
from backend.repositories.strength_plans import (
    StrengthPlansRepository,
)
from backend.repositories.strength_workouts import (
    StrengthWorkoutExercisesRepository,
    StrengthWorkoutsRepository,
)
from backend.services.strength_plan import (
    StrengthPlanInput,
    StrengthPlanService,
)


router = APIRouter(
    prefix="/strength",
    tags=["strength"],
)


class StrengthPlanRequest(BaseModel):
    start_date: date

    goal: str = Field(
        pattern=(
            "^(hypertrophy|strength|"
            "general_fitness)$"
        )
    )

    experience_level: str = Field(
        pattern=(
            "^(beginner|intermediate|"
            "advanced)$"
        )
    )

    sessions_per_week: int = Field(
        ge=2,
        le=4,
    )

    total_weeks: int = Field(
        default=8,
        ge=4,
        le=24,
    )

    replace_active: bool = False


def _generate_strength_plan(
    request: StrengthPlanRequest,
) -> dict:
    try:
        return StrengthPlanService().build(
            StrengthPlanInput(
                start_date=request.start_date,
                goal=request.goal,
                experience_level=(
                    request.experience_level
                ),
                sessions_per_week=(
                    request.sessions_per_week
                ),
                total_weeks=request.total_weeks,
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=str(exc),
        ) from exc


def _plan_payload(
    *,
    user_id: str,
    generated: dict,
) -> dict:
    return {
        "user_id": user_id,
        "goal": generated["goal"],
        "experience_level": generated[
            "experience_level"
        ],
        "program_style": generated[
            "program_style"
        ],
        "sessions_per_week": generated[
            "sessions_per_week"
        ],
        "start_date": generated[
            "start_date"
        ],
        "total_weeks": generated[
            "total_weeks"
        ],
        "status": "active",
    }


def _persist_strength_plan(
    *,
    user_id: str,
    generated: dict,
    plans_repo: StrengthPlansRepository,
    workouts_repo: StrengthWorkoutsRepository,
    exercises_repo:
        StrengthWorkoutExercisesRepository,
) -> dict:
    plan = plans_repo.create(
        _plan_payload(
            user_id=user_id,
            generated=generated,
        )
    )

    if not plan or not plan.get("id"):
        raise RepositoryError(
            "Strength plan was not persisted"
        )

    plan_id = plan["id"]

    try:
        workout_payloads = []

        for workout in generated["workouts"]:
            workout_payloads.append(
                {
                    "user_id": user_id,
                    "strength_plan_id": plan_id,
                    "scheduled_date": workout[
                        "scheduled_date"
                    ],
                    "training_week": workout[
                        "training_week"
                    ],
                    "workout_index": workout[
                        "workout_index"
                    ],
                    "title": workout["title"],
                    "focus": workout["focus"],
                    "status": workout[
                        "status"
                    ],
                    "estimated_duration_minutes":
                        workout[
                            "estimated_duration_minutes"
                        ],
                }
            )

        created_workouts = (
            workouts_repo.create_many(
                workout_payloads
            )
        )

        expected = len(workout_payloads)

        if len(created_workouts) != expected:
            raise RepositoryError(
                "Not all strength workouts "
                "were persisted"
            )

        workout_by_key = {
            (
                int(item["training_week"]),
                int(item["workout_index"]),
            ): item
            for item in created_workouts
        }

        exercise_payloads = []

        for workout in generated["workouts"]:
            key = (
                int(workout["training_week"]),
                int(workout["workout_index"]),
            )

            persisted_workout = (
                workout_by_key.get(key)
            )

            if (
                not persisted_workout
                or not persisted_workout.get("id")
            ):
                raise RepositoryError(
                    "Persisted strength workout "
                    "cannot be matched"
                )

            workout_id = persisted_workout[
                "id"
            ]

            for exercise in workout[
                "exercises"
            ]:
                exercise_payloads.append(
                    {
                        "user_id": user_id,
                        "strength_workout_id":
                            workout_id,
                        "position": exercise[
                            "position"
                        ],
                        "exercise_key": exercise[
                            "exercise_key"
                        ],
                        "exercise_name": exercise[
                            "exercise_name"
                        ],
                        "movement_pattern":
                            exercise[
                                "movement_pattern"
                            ],
                        "target_sets": exercise[
                            "target_sets"
                        ],
                        "target_reps_min":
                            exercise[
                                "target_reps_min"
                            ],
                        "target_reps_max":
                            exercise[
                                "target_reps_max"
                            ],
                        "target_rir": exercise[
                            "target_rir"
                        ],
                        "rest_seconds": exercise[
                            "rest_seconds"
                        ],
                        "prescribed_load_kg":
                            exercise[
                                "prescribed_load_kg"
                            ],
                    }
                )

        created_exercises = (
            exercises_repo.create_many(
                exercise_payloads
            )
        )

        if (
            len(created_exercises)
            != len(exercise_payloads)
        ):
            raise RepositoryError(
                "Not all strength exercises "
                "were persisted"
            )

        return {
            "plan": plan,
            "workouts": created_workouts,
            "workout_count":
                len(created_workouts),
            "exercise_count":
                len(created_exercises),
        }

    except Exception:
        try:
            plans_repo.delete(
                plan_id,
                user_id,
            )
        except RepositoryError:
            pass

        raise


@router.post("/plans/preview")
def preview_strength_plan(
    request: StrengthPlanRequest,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
):
    generated = _generate_strength_plan(
        request
    )

    return {
        "preview": True,
        "plan": generated,
    }


@router.post(
    "/plans",
    status_code=status.HTTP_201_CREATED,
)
def create_strength_plan(
    request: StrengthPlanRequest,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    plans_repo: StrengthPlansRepository = Depends(
        get_strength_plans_repository
    ),
    workouts_repo:
        StrengthWorkoutsRepository = Depends(
            get_strength_workouts_repository
        ),
    exercises_repo:
        StrengthWorkoutExercisesRepository = Depends(
            get_strength_workout_exercises_repository
        ),
):
    generated = _generate_strength_plan(
        request
    )

    try:
        existing = plans_repo.list_for_user(
            current_user.id
        )

        active = [
            item
            for item in existing
            if item.get("status") == "active"
        ]

        if active and not request.replace_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Hai già un programma palestra "
                    "attivo. Conferma la sostituzione "
                    "per crearne uno nuovo."
                ),
            )

        result = _persist_strength_plan(
            user_id=current_user.id,
            generated=generated,
            plans_repo=plans_repo,
            workouts_repo=workouts_repo,
            exercises_repo=exercises_repo,
        )

        replaced_plan_ids = []

        if request.replace_active:
            new_id = result["plan"]["id"]

            for item in active:
                old_id = item.get("id")

                if (
                    not old_id
                    or old_id == new_id
                ):
                    continue

                plans_repo.delete(
                    old_id,
                    current_user.id,
                )

                replaced_plan_ids.append(
                    old_id
                )

        return {
            "created": True,
            **result,
            "replaced_plan_ids":
                replaced_plan_ids,
        }

    except HTTPException:
        raise

    except RepositoryError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=str(exc),
        ) from exc


@router.get("/plans")
def list_strength_plans(
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    plans_repo: StrengthPlansRepository = Depends(
        get_strength_plans_repository
    ),
):
    try:
        items = plans_repo.list_for_user(
            current_user.id
        )

        return {
            "count": len(items),
            "items": items,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=str(exc),
        ) from exc
