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
    get_strength_workout_logs_repository,
    get_strength_set_logs_repository,
    get_strength_progression_history_repository,
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
from backend.repositories.strength_logs import (
    StrengthSetLogsRepository,
    StrengthWorkoutLogsRepository,
)
from backend.repositories.strength_progression_history import (
    StrengthProgressionHistoryRepository,
)
from backend.services.strength_plan import (
    StrengthPlanInput,
    StrengthPlanService,
)
from backend.services.strength_outcome import (
    StrengthOutcomeService,
)
from backend.services.strength_progression import (
    StrengthProgressionService,
)


router = APIRouter(
    prefix="/strength",
    tags=["strength"],
)


class StrengthSetLogRequest(BaseModel):
    reps: int = Field(gt=0)
    load_kg: float = Field(default=0, ge=0)
    rir: float | None = Field(
        default=None,
        ge=0,
        le=6,
    )


class StrengthExerciseLogRequest(BaseModel):
    exercise_id: str = Field(min_length=1)
    sets: list[StrengthSetLogRequest] = Field(
        min_length=1,
        max_length=10,
    )


class StrengthWorkoutLogRequest(BaseModel):
    performed_date: date

    duration_minutes: int | None = Field(
        default=None,
        gt=0,
    )

    notes: str | None = Field(
        default=None,
        max_length=2000,
    )

    exercises: list[
        StrengthExerciseLogRequest
    ] = Field(min_length=1)


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

@router.post(
    "/workouts/{workout_id}/log",
    status_code=status.HTTP_201_CREATED,
)
def log_strength_workout(
    workout_id: str,
    request: StrengthWorkoutLogRequest,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    workouts_repo:
        StrengthWorkoutsRepository = Depends(
            get_strength_workouts_repository
        ),
    exercises_repo:
        StrengthWorkoutExercisesRepository = Depends(
            get_strength_workout_exercises_repository
        ),
    workout_logs_repo:
        StrengthWorkoutLogsRepository = Depends(
            get_strength_workout_logs_repository
        ),
    set_logs_repo:
        StrengthSetLogsRepository = Depends(
            get_strength_set_logs_repository
        ),
):
    try:
        workout = workouts_repo.get(
            current_user.id,
            workout_id,
        )

        if not workout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workout palestra non trovato.",
            )

        existing_log = (
            workout_logs_repo.get_for_workout(
                current_user.id,
                workout_id,
            )
        )

        if existing_log:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Questo workout è già stato "
                    "registrato."
                ),
            )

        planned_exercises = (
            exercises_repo.list_for_workout(
                current_user.id,
                workout_id,
            )
        )

        allowed_ids = {
            str(item["id"])
            for item in planned_exercises
            if item.get("id")
        }

        submitted_ids = [
            item.exercise_id
            for item in request.exercises
        ]

        if len(submitted_ids) != len(
            set(submitted_ids)
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Lo stesso esercizio non può "
                    "comparire due volte."
                ),
            )

        if any(
            item not in allowed_ids
            for item in submitted_ids
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Uno o più esercizi non "
                    "appartengono a questo workout."
                ),
            )

        workout_log = workout_logs_repo.create(
            {
                "user_id": current_user.id,
                "strength_workout_id": workout_id,
                "performed_date": str(
                    request.performed_date
                ),
                "duration_minutes":
                    request.duration_minutes,
                "notes": request.notes,
            }
        )

        if (
            not workout_log
            or not workout_log.get("id")
        ):
            raise RepositoryError(
                "Strength workout log "
                "was not persisted"
            )

        log_id = workout_log["id"]

        try:
            payloads = []

            for exercise in request.exercises:
                for set_index, set_item in enumerate(
                    exercise.sets,
                    start=1,
                ):
                    payloads.append(
                        {
                            "user_id":
                                current_user.id,
                            "strength_workout_log_id":
                                log_id,
                            "strength_workout_exercise_id":
                                exercise.exercise_id,
                            "set_index": set_index,
                            "reps": set_item.reps,
                            "load_kg":
                                set_item.load_kg,
                            "rir": set_item.rir,
                        }
                    )

            created_sets = (
                set_logs_repo.create_many(
                    payloads
                )
            )

            if len(created_sets) != len(
                payloads
            ):
                raise RepositoryError(
                    "Not all strength sets "
                    "were persisted"
                )

            updated_workout = (
                workouts_repo.update_status(
                    user_id=current_user.id,
                    workout_id=workout_id,
                    status="completed",
                )
            )

            if not updated_workout:
                raise RepositoryError(
                    "Strength workout status "
                    "was not updated"
                )

            return {
                "logged": True,
                "workout": updated_workout,
                "workout_log": workout_log,
                "set_count": len(created_sets),
                "sets": created_sets,
            }

        except Exception:
            try:
                workout_logs_repo.delete(
                    log_id,
                    current_user.id,
                )
            except RepositoryError:
                pass

            raise

    except HTTPException:
        raise

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

@router.get(
    "/workouts/{workout_id}/outcome",
)
def get_strength_workout_outcome(
    workout_id: str,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    workouts_repo:
        StrengthWorkoutsRepository = Depends(
            get_strength_workouts_repository
        ),
    exercises_repo:
        StrengthWorkoutExercisesRepository = Depends(
            get_strength_workout_exercises_repository
        ),
    workout_logs_repo:
        StrengthWorkoutLogsRepository = Depends(
            get_strength_workout_logs_repository
        ),
    set_logs_repo:
        StrengthSetLogsRepository = Depends(
            get_strength_set_logs_repository
        ),
):
    try:
        workout = workouts_repo.get(
            current_user.id,
            workout_id,
        )

        if not workout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Workout palestra non trovato."
                ),
            )

        workout_log = (
            workout_logs_repo.get_for_workout(
                current_user.id,
                workout_id,
            )
        )

        if not workout_log:
            return {
                "status": "pending",
                "workout": workout,
                "workout_log": None,
                "outcome": None,
                "message": (
                    "Il workout non è ancora "
                    "stato registrato."
                ),
            }

        planned_exercises = (
            exercises_repo.list_for_workout(
                current_user.id,
                workout_id,
            )
        )

        set_logs = (
            set_logs_repo.list_for_workout_log(
                current_user.id,
                workout_log["id"],
            )
        )

        try:
            outcome = (
                StrengthOutcomeService().evaluate(
                    planned_exercises=
                        planned_exercises,
                    set_logs=set_logs,
                )
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_CONTENT
                ),
                detail=str(exc),
            ) from exc

        return {
            "status": "evaluated",
            "workout": workout,
            "workout_log": workout_log,
            "outcome": outcome,
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

@router.get(
    "/workouts/{workout_id}/progression-preview",
)
def preview_strength_progression(
    workout_id: str,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    workouts_repo:
        StrengthWorkoutsRepository = Depends(
            get_strength_workouts_repository
        ),
    exercises_repo:
        StrengthWorkoutExercisesRepository = Depends(
            get_strength_workout_exercises_repository
        ),
    workout_logs_repo:
        StrengthWorkoutLogsRepository = Depends(
            get_strength_workout_logs_repository
        ),
    set_logs_repo:
        StrengthSetLogsRepository = Depends(
            get_strength_set_logs_repository
        ),
):
    try:
        workout = workouts_repo.get(
            current_user.id,
            workout_id,
        )

        if not workout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Workout palestra non trovato."
                ),
            )

        workout_log = (
            workout_logs_repo.get_for_workout(
                current_user.id,
                workout_id,
            )
        )

        if not workout_log:
            return {
                "status": "pending",
                "workout": workout,
                "proposals": [],
                "message": (
                    "Registra prima il workout "
                    "per calcolare la progressione."
                ),
            }

        planned_exercises = (
            exercises_repo.list_for_workout(
                current_user.id,
                workout_id,
            )
        )

        set_logs = (
            set_logs_repo.list_for_workout_log(
                current_user.id,
                workout_log["id"],
            )
        )

        outcome = (
            StrengthOutcomeService().evaluate(
                planned_exercises=
                    planned_exercises,
                set_logs=set_logs,
            )
        )

        logs_by_exercise = {}

        for item in set_logs:
            exercise_id = str(
                item[
                    "strength_workout_exercise_id"
                ]
            )

            logs_by_exercise.setdefault(
                exercise_id,
                [],
            ).append(item)

        outcome_by_exercise = {
            str(item["exercise_id"]): item
            for item in outcome["exercises"]
        }

        plan_workouts = (
            workouts_repo.list_for_plan(
                current_user.id,
                workout["strength_plan_id"],
            )
        )

        future_workouts = [
            item
            for item in plan_workouts
            if (
                str(item["scheduled_date"])
                > str(workout["scheduled_date"])
                and item.get("status")
                == "planned"
            )
        ]

        future_workouts.sort(
            key=lambda item: (
                str(item["scheduled_date"]),
                int(
                    item.get(
                        "workout_index",
                        0,
                    )
                ),
            )
        )

        next_by_key = {}

        for future_workout in future_workouts:
            future_exercises = (
                exercises_repo.list_for_workout(
                    current_user.id,
                    future_workout["id"],
                )
            )

            for future_exercise in (
                future_exercises
            ):
                key = future_exercise.get(
                    "exercise_key"
                )

                if (
                    key
                    and key not in next_by_key
                ):
                    next_by_key[key] = {
                        "workout":
                            future_workout,
                        "exercise":
                            future_exercise,
                    }

        service = StrengthProgressionService()
        proposals = []

        for planned in planned_exercises:
            exercise_id = str(
                planned["id"]
            )

            exercise_outcome = (
                outcome_by_exercise.get(
                    exercise_id
                )
            )

            if not exercise_outcome:
                continue

            proposal = service.preview(
                planned_exercise=planned,
                exercise_outcome=
                    exercise_outcome,
                set_logs=logs_by_exercise.get(
                    exercise_id,
                    [],
                ),
            )

            next_exposure = next_by_key.get(
                planned.get("exercise_key")
            )

            proposal["next_exposure"] = (
                {
                    "workout_id":
                        next_exposure[
                            "workout"
                        ]["id"],
                    "scheduled_date":
                        next_exposure[
                            "workout"
                        ]["scheduled_date"],
                    "exercise_id":
                        next_exposure[
                            "exercise"
                        ]["id"],
                    "current_prescribed_load_kg":
                        next_exposure[
                            "exercise"
                        ].get(
                            "prescribed_load_kg"
                        ),
                }
                if next_exposure
                else None
            )

            proposals.append(proposal)

        actionable = [
            item
            for item in proposals
            if (
                item["action"]
                != "maintain"
                and item["next_exposure"]
                is not None
            )
        ]

        return {
            "status": "preview",
            "workout": workout,
            "workout_outcome":
                outcome["outcome"],
            "proposal_count":
                len(proposals),
            "actionable_count":
                len(actionable),
            "proposals": proposals,
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

@router.post(
    "/workouts/{workout_id}/progression/"
    "{exercise_id}/apply",
)
def apply_strength_progression(
    workout_id: str,
    exercise_id: str,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    workouts_repo:
        StrengthWorkoutsRepository = Depends(
            get_strength_workouts_repository
        ),
    exercises_repo:
        StrengthWorkoutExercisesRepository = Depends(
            get_strength_workout_exercises_repository
        ),
    workout_logs_repo:
        StrengthWorkoutLogsRepository = Depends(
            get_strength_workout_logs_repository
        ),
    set_logs_repo:
        StrengthSetLogsRepository = Depends(
            get_strength_set_logs_repository
        ),
    history_repo:
        StrengthProgressionHistoryRepository = Depends(
            get_strength_progression_history_repository
        ),
):
    try:
        workout = workouts_repo.get(
            current_user.id,
            workout_id,
        )

        if not workout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Workout palestra non trovato."
                ),
            )

        existing = (
            history_repo.get_for_source_exercise(
                current_user.id,
                exercise_id,
            )
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "La progressione di questo "
                    "esercizio è già stata gestita."
                ),
            )

        planned_exercises = (
            exercises_repo.list_for_workout(
                current_user.id,
                workout_id,
            )
        )

        source_exercise = next(
            (
                item
                for item in planned_exercises
                if str(item.get("id"))
                == str(exercise_id)
            ),
            None,
        )

        if not source_exercise:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Esercizio non trovato "
                    "nel workout sorgente."
                ),
            )

        workout_log = (
            workout_logs_repo.get_for_workout(
                current_user.id,
                workout_id,
            )
        )

        if not workout_log:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Registra prima il workout "
                    "per applicare la progressione."
                ),
            )

        set_logs = (
            set_logs_repo.list_for_workout_log(
                current_user.id,
                workout_log["id"],
            )
        )

        outcome = (
            StrengthOutcomeService().evaluate(
                planned_exercises=
                    planned_exercises,
                set_logs=set_logs,
            )
        )

        exercise_outcome = next(
            (
                item
                for item in outcome["exercises"]
                if str(item["exercise_id"])
                == str(exercise_id)
            ),
            None,
        )

        if not exercise_outcome:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Outcome esercizio "
                    "non disponibile."
                ),
            )

        source_set_logs = [
            item
            for item in set_logs
            if str(
                item.get(
                    "strength_workout_exercise_id"
                )
            )
            == str(exercise_id)
        ]

        proposal = (
            StrengthProgressionService().preview(
                planned_exercise=
                    source_exercise,
                exercise_outcome=
                    exercise_outcome,
                set_logs=source_set_logs,
            )
        )

        if proposal["current_load_kg"] <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Non esiste un carico esterno "
                    "valido da applicare."
                ),
            )

        plan_workouts = (
            workouts_repo.list_for_plan(
                current_user.id,
                workout["strength_plan_id"],
            )
        )

        future_workouts = [
            item
            for item in plan_workouts
            if (
                str(item["scheduled_date"])
                > str(workout["scheduled_date"])
                and item.get("status")
                == "planned"
            )
        ]

        future_workouts.sort(
            key=lambda item: (
                str(item["scheduled_date"]),
                int(
                    item.get(
                        "workout_index",
                        0,
                    )
                ),
            )
        )

        target_workout = None
        target_exercise = None

        source_key = source_exercise.get(
            "exercise_key"
        )

        for future_workout in future_workouts:
            future_exercises = (
                exercises_repo.list_for_workout(
                    current_user.id,
                    future_workout["id"],
                )
            )

            match = next(
                (
                    item
                    for item in future_exercises
                    if item.get("exercise_key")
                    == source_key
                ),
                None,
            )

            if match:
                target_workout = future_workout
                target_exercise = match
                break

        if not target_exercise:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Non esiste una prossima "
                    "esposizione a questo esercizio."
                ),
            )

        target_guard = (
            history_repo.get_for_target_exercise(
                current_user.id,
                target_exercise["id"],
            )
        )

        if target_guard:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "La prossima esposizione è già "
                    "stata modificata da una "
                    "progressione precedente."
                ),
            )

        before_load = target_exercise.get(
            "prescribed_load_kg"
        )

        after_load = proposal[
            "proposed_load_kg"
        ]

        atomic_result = history_repo.apply_atomic(
            user_id=current_user.id,
            strength_plan_id=
                workout["strength_plan_id"],
            source_workout_id=workout_id,
            source_exercise_id=
                source_exercise["id"],
            target_workout_id=
                target_workout["id"],
            target_exercise_id=
                target_exercise["id"],
            exercise_key=source_key,
            outcome=
                exercise_outcome["outcome"],
            action=proposal["action"],
            observed_load_kg=
                proposal["current_load_kg"],
            expected_before_load_kg=
                before_load,
            after_load_kg=after_load,
        )

        if not atomic_result.get("applied"):
            reason = atomic_result.get(
                "reason"
            )

            messages = {
                "stale_target": (
                    "Il carico della prossima "
                    "esposizione è cambiato dopo "
                    "la preview. Ricalcola la "
                    "progressione."
                ),
                "source_already_handled": (
                    "La progressione di questo "
                    "esercizio è già stata gestita."
                ),
                "target_already_handled": (
                    "La prossima esposizione è già "
                    "stata modificata."
                ),
                "concurrent_conflict": (
                    "Un'altra progressione è stata "
                    "applicata nello stesso momento. "
                    "Ricalcola la preview."
                ),
                "target_not_available": (
                    "La prossima esposizione non è "
                    "più disponibile."
                ),
                "exercise_key_mismatch": (
                    "L'esercizio target non "
                    "corrisponde più alla preview."
                ),
            }

            raise HTTPException(
                status_code=
                    status.HTTP_409_CONFLICT,
                detail=messages.get(
                    reason,
                    (
                        "La progressione non può "
                        "essere applicata allo "
                        "stato corrente."
                    ),
                ),
            )

        history = atomic_result.get(
            "history"
        )

        updated_exercise = (
            atomic_result.get(
                "target_exercise"
            )
        )

        if (
            not history
            or not updated_exercise
        ):
            raise RepositoryError(
                "Atomic strength progression "
                "returned incomplete data"
            )

        return {
            "applied": True,
            "proposal": proposal,
            "history": history,
            "target_workout":
                target_workout,
            "target_exercise":
                updated_exercise,
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


@router.get(
    "/plans/{plan_id}/progression-history",
)
def list_strength_progression_history(
    plan_id: str,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    history_repo:
        StrengthProgressionHistoryRepository = Depends(
            get_strength_progression_history_repository
        ),
):
    try:
        items = history_repo.list_for_plan(
            current_user.id,
            plan_id,
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

@router.get(
    "/plans/{plan_id}",
)
def get_strength_plan_detail(
    plan_id: str,
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
    try:
        plan = plans_repo.get(
            plan_id,
            current_user.id,
        )

        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Programma palestra non trovato."
                ),
            )

        workouts = workouts_repo.list_for_plan(
            current_user.id,
            plan_id,
        )

        items = []

        for workout in workouts:
            workout_id = workout.get("id")

            exercises = (
                exercises_repo.list_for_workout(
                    current_user.id,
                    workout_id,
                )
                if workout_id
                else []
            )

            items.append(
                {
                    **workout,
                    "exercises": exercises,
                }
            )

        return {
            "plan": plan,
            "workout_count": len(items),
            "workouts": items,
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

@router.get(
    "/plans/{plan_id}/history",
)
def get_strength_plan_history(
    plan_id: str,
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
    workout_logs_repo:
        StrengthWorkoutLogsRepository = Depends(
            get_strength_workout_logs_repository
        ),
    set_logs_repo:
        StrengthSetLogsRepository = Depends(
            get_strength_set_logs_repository
        ),
    history_repo:
        StrengthProgressionHistoryRepository = Depends(
            get_strength_progression_history_repository
        ),
):
    try:
        plan = plans_repo.get(
            plan_id,
            current_user.id,
        )

        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Programma palestra non trovato."
                ),
            )

        workouts = workouts_repo.list_for_plan(
            current_user.id,
            plan_id,
        )

        progression_rows = (
            history_repo.list_for_plan(
                current_user.id,
                plan_id,
            )
        )

        progressions_by_workout = {}

        for item in progression_rows:
            source_id = str(
                item.get(
                    "source_workout_id",
                    "",
                )
            )

            progressions_by_workout.setdefault(
                source_id,
                [],
            ).append(item)

        items = []

        for workout in workouts:
            if workout.get("status") != "completed":
                continue

            workout_id = str(workout["id"])

            workout_log = (
                workout_logs_repo.get_for_workout(
                    current_user.id,
                    workout_id,
                )
            )

            if not workout_log:
                continue

            planned_exercises = (
                exercises_repo.list_for_workout(
                    current_user.id,
                    workout_id,
                )
            )

            set_logs = (
                set_logs_repo.list_for_workout_log(
                    current_user.id,
                    workout_log["id"],
                )
            )

            outcome = (
                StrengthOutcomeService().evaluate(
                    planned_exercises=
                        planned_exercises,
                    set_logs=set_logs,
                )
            )

            sets_by_exercise = {}

            for set_item in set_logs:
                exercise_id = str(
                    set_item[
                        "strength_workout_exercise_id"
                    ]
                )

                sets_by_exercise.setdefault(
                    exercise_id,
                    [],
                ).append(set_item)

            exercise_items = []

            for exercise in planned_exercises:
                exercise_id = str(
                    exercise["id"]
                )

                exercise_items.append(
                    {
                        **exercise,
                        "sets":
                            sets_by_exercise.get(
                                exercise_id,
                                [],
                            ),
                    }
                )

            items.append(
                {
                    "workout": workout,
                    "workout_log": workout_log,
                    "exercises": exercise_items,
                    "outcome": outcome,
                    "progressions":
                        progressions_by_workout.get(
                            workout_id,
                            [],
                        ),
                }
            )

        items.sort(
            key=lambda item: (
                str(
                    item["workout_log"].get(
                        "performed_date",
                        "",
                    )
                ),
                str(
                    item["workout"].get(
                        "scheduled_date",
                        "",
                    )
                ),
            ),
            reverse=True,
        )

        return {
            "plan_id": plan_id,
            "count": len(items),
            "items": items,
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

