from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from pydantic import BaseModel

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_planned_activities_repository,
    get_strength_set_logs_repository,
    get_strength_workout_exercises_repository,
    get_strength_workout_logs_repository,
    get_strength_workouts_repository,
    get_strength_plans_repository,
    get_training_coach_adjustments_repository,
    get_training_coach_preferences_repository,
)
from backend.repositories.activities import (
    ActivitiesRepository,
)
from backend.repositories.base import RepositoryError
from backend.repositories.planned_activities import (
    PlannedActivitiesRepository,
)
from backend.repositories.strength_logs import (
    StrengthSetLogsRepository,
    StrengthWorkoutLogsRepository,
)
from backend.repositories.strength_workouts import (
    StrengthWorkoutExercisesRepository,
    StrengthWorkoutsRepository,
)
from backend.repositories.strength_plans import StrengthPlansRepository
from backend.repositories.training_coach_adjustments import (
    TrainingCoachAdjustmentsRepository,
)
from backend.repositories.training_coach_preferences import (
    TrainingCoachPreferencesRepository,
)
from backend.services.adaptive_training_coach import (
    AdaptiveTrainingCoachService,
)
from backend.services.training_load import (
    TrainingLoadService,
)
from backend.services.skipped_session_review import (
    SkippedSessionReviewService,
)


router = APIRouter(
    prefix="/coach",
    tags=["training-coach"],
)


class CoachReconcileRequest(BaseModel):
    as_of: date | None = None


class CoachRecoveryApplyRequest(BaseModel):
    suggested_date: date
    original_date: date


class CoachPreferencesUpdate(BaseModel):
    priority: Literal[
        "gym",
        "balanced",
        "running",
    ]


RUNNING_TYPES = {
    "corsa",
    "running",
    "run",
    "jogging",
}


def _normalized(value: object) -> str:
    return " ".join(
        str(value or "")
        .strip()
        .casefold()
        .replace("_", " ")
        .split()
    )


def _is_running_planned(
    item: dict,
) -> bool:
    return (
        _normalized(
            item.get("activity_type")
        )
        in RUNNING_TYPES
    )


def _coach_context(
    *,
    user_id: str,
    as_of: date,
    activities_repo: ActivitiesRepository,
    planned_repo: PlannedActivitiesRepository,
    workouts_repo: StrengthWorkoutsRepository,
    exercises_repo:
        StrengthWorkoutExercisesRepository,
    workout_logs_repo:
        StrengthWorkoutLogsRepository,
    set_logs_repo: StrengthSetLogsRepository,
    priority: str = "balanced",
) -> dict:
    recent_start = as_of - timedelta(days=3)
    future_end = as_of + timedelta(days=3)

    activities = activities_repo.list_date_range(
        user_id,
        recent_start,
        as_of,
    )

    load_service = TrainingLoadService()
    events = []

    planned_cache: dict[str, dict | None] = {}

    for activity in activities:
        planned = None
        planned_id = activity.get(
            "planned_activity_id"
        )

        if planned_id:
            key = str(planned_id)

            if key not in planned_cache:
                planned_cache[key] = planned_repo.get(
                    key,
                    user_id,
                )

            planned = planned_cache[key]

        event = load_service.activity_event(
            activity=activity,
            planned=planned,
        )

        if event is not None:
            events.append(event)

    strength_logs = (
        workout_logs_repo.list_date_range(
            user_id,
            recent_start,
            as_of,
        )
    )

    for workout_log in strength_logs:
        workout_id = workout_log.get(
            "strength_workout_id"
        )

        if not workout_id:
            continue

        workout = workouts_repo.get(
            user_id,
            workout_id,
        )

        if not workout:
            continue

        exercises = exercises_repo.list_for_workout(
            user_id,
            workout_id,
        )
        set_logs = set_logs_repo.list_for_workout_log(
            user_id,
            workout_log["id"],
        )

        event = load_service.strength_event(
            workout=workout,
            workout_log=workout_log,
            exercises=exercises,
            set_logs=set_logs,
        )

        if event is not None:
            events.append(event)

    upcoming_strength = [
        item
        for item in workouts_repo.list_date_range(
            user_id,
            as_of,
            future_end,
        )
        if item.get("status") == "planned"
    ]

    strength_exercises = {
        str(workout["id"]):
            exercises_repo.list_for_workout(
                user_id,
                workout["id"],
            )
        for workout in upcoming_strength
    }

    upcoming_running = [
        item
        for item in planned_repo.list_range(
            user_id,
            as_of,
            future_end,
        )
        if (
            item.get("status") == "planned"
            and _is_running_planned(item)
        )
    ]

    skipped_running = [
        item
        for item in planned_repo.list_range(
            user_id, recent_start, as_of,
        )
        if item.get("status") == "skipped"
        and _is_running_planned(item)
    ]
    skipped_strength = [
        item
        for item in workouts_repo.list_date_range(
            user_id, recent_start, as_of,
        )
        if item.get("status") == "skipped"
    ]
    recovery_future_end = as_of + timedelta(days=8)
    recovery_alerts = SkippedSessionReviewService().build(
        as_of=as_of,
        running_sessions=skipped_running,
        strength_workouts=skipped_strength,
        upcoming_running=planned_repo.list_range(
            user_id, as_of, recovery_future_end,
        ),
        upcoming_strength=workouts_repo.list_date_range(
            user_id, as_of, recovery_future_end,
        ),
        recent_events=events,
    )

    proposals = (
        AdaptiveTrainingCoachService().build(
            recent_events=events,
            upcoming_strength=upcoming_strength,
            strength_exercises=
                strength_exercises,
            upcoming_running=upcoming_running,
            priority=priority,
        )
    )

    return {
        "as_of": str(as_of),
        "recent_start": str(recent_start),
        "future_end": str(future_end),
        "events": events,
        "upcoming_strength":
            upcoming_strength,
        "strength_exercises":
            strength_exercises,
        "upcoming_running":
            upcoming_running,
        "proposals": proposals,
        "recovery_alerts": recovery_alerts,
    }


def _adjustment_payload(
    *,
    user_id: str,
    proposal: dict,
) -> dict:
    return {
        "user_id": user_id,
        "source_kind":
            proposal["source_kind"],
        "source_id":
            proposal["source_id"],
        "source_date":
            proposal["source_date"],
        "target_kind":
            proposal["target_kind"],
        "target_id":
            proposal["target_id"],
        "target_date":
            proposal["target_date"],
        "action": proposal["action"],
        "severity":
            proposal["severity"],
        "scope": proposal["scope"],
        "decision": "proposed",
        "title": proposal["title"],
        "message": proposal["message"],
        "proposed_changes":
            proposal["proposed_changes"],
        "before_state":
            proposal.get("before_state"),
    }


def _apply_strength_changes(
    *,
    user_id: str,
    target_workout_id: str,
    proposed_changes: dict,
    workouts_repo: StrengthWorkoutsRepository,
    exercises_repo:
        StrengthWorkoutExercisesRepository,
    before_state: dict | None = None,
) -> dict:
    workout = workouts_repo.get(
        user_id,
        target_workout_id,
    )

    if (
        not workout
        or workout.get("status") != "planned"
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "La seduta palestra target non è "
                "più modificabile."
            ),
        )

    # Validate the full adjustment before updating any exercise.
    # This avoids applying only half of an obsolete proposal.
    if before_state:
        for field in ("scheduled_date", "focus"):
            if (
                field in before_state
                and workout.get(field) != before_state[field]
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "La seduta è cambiata. "
                        "Aggiorna il Coach prima di applicare."
                    ),
                )

    validated_updates = []

    for item in (
        proposed_changes.get(
            "exercise_updates"
        )
        or []
    ):
        exercise_id = str(
            item.get("exercise_id")
            or ""
        )

        if not exercise_id:
            continue

        exercise = exercises_repo.get(
            user_id,
            exercise_id,
        )

        if (
            not exercise
            or str(
                exercise.get(
                    "strength_workout_id"
                )
            )
            != target_workout_id
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "Il programma è cambiato. "
                    "Aggiorna il Coach prima di applicare."
                ),
            )

        # The proposal records the values it was calculated from.
        # Refuse to overwrite subsequent user edits.
        for before_field, current_field in (
            ("before_load_kg", "prescribed_load_kg"),
            ("before_target_sets", "target_sets"),
        ):
            if (
                before_field in item
                and exercise.get(current_field) != item[before_field]
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Un esercizio è cambiato. "
                        "Aggiorna il Coach prima di applicare."
                    ),
                )

        payload = {}

        if (
            item.get(
                "prescribed_load_kg"
            )
            is not None
        ):
            payload[
                "prescribed_load_kg"
            ] = float(
                item[
                    "prescribed_load_kg"
                ]
            )

        if item.get("target_sets") is not None:
            payload["target_sets"] = int(
                item["target_sets"]
            )

        if payload:
            validated_updates.append((exercise_id, payload))

    updated_exercises = []
    for exercise_id, payload in validated_updates:
        updated = exercises_repo.update(
            user_id=user_id,
            exercise_id=exercise_id,
            payload=payload,
        )

        if not updated:
            raise RepositoryError(
                "Coach strength update was "
                "not persisted"
            )

        updated_exercises.append(updated)

    return {
        "workout": workout,
        "exercises": updated_exercises,
    }


def _apply_running_changes(
    *,
    user_id: str,
    target_id: str,
    proposed_changes: dict,
    planned_repo:
        PlannedActivitiesRepository,
    before_state: dict | None = None,
) -> dict:
    planned = planned_repo.get(
        target_id,
        user_id,
    )

    if (
        not planned
        or planned.get("status") != "planned"
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "La seduta corsa target non è "
                "più modificabile."
            ),
        )

    # Do not overwrite manual edits made after the Coach suggestion.
    # Legacy adjustments may not have a complete before_state snapshot.
    if before_state:
        for field in (
            "scheduled_date",
            "distance_meters",
            "duration_minutes",
            "intensity",
        ):
            if (
                field in before_state
                and planned.get(field) != before_state[field]
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "La seduta è cambiata. "
                        "Aggiorna il Coach prima di applicare."
                    ),
                )

    allowed = {
        "distance_meters",
        "duration_minutes",
        "intensity",
        "scheduled_date",
    }

    changes = {
        key: value
        for key, value
        in proposed_changes.items()
        if key in allowed
    }

    if not changes:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "La proposta non contiene "
                "modifiche applicabili."
            ),
        )

    updated = planned_repo.update(
        target_id,
        user_id,
        changes,
    )

    if not updated:
        raise RepositoryError(
            "Coach running update was "
            "not persisted"
        )

    return updated


def _apply_adjustment(
    *,
    user_id: str,
    adjustment: dict,
    workouts_repo: StrengthWorkoutsRepository,
    exercises_repo:
        StrengthWorkoutExercisesRepository,
    planned_repo: PlannedActivitiesRepository,
) -> dict:
    target_kind = adjustment.get(
        "target_kind"
    )
    target_id = str(
        adjustment.get("target_id")
        or ""
    )
    changes = dict(
        adjustment.get(
            "proposed_changes"
        )
        or {}
    )

    if target_kind == "strength_workout":
        return _apply_strength_changes(
            user_id=user_id,
            target_workout_id=target_id,
            proposed_changes=changes,
            workouts_repo=workouts_repo,
            exercises_repo=exercises_repo,
            before_state=adjustment.get("before_state"),
        )

    if target_kind == "planned_activity":
        return _apply_running_changes(
            user_id=user_id,
            target_id=target_id,
            proposed_changes=changes,
            planned_repo=planned_repo,
            before_state=adjustment.get("before_state"),
        )

    raise HTTPException(
        status_code=(
            status.HTTP_422_UNPROCESSABLE_CONTENT
        ),
        detail="Target Coach non supportato.",
    )


@router.get("/preferences")
def get_training_coach_preferences(
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    preferences_repo:
        TrainingCoachPreferencesRepository = Depends(
            get_training_coach_preferences_repository
        ),
):
    try:
        return {
            "priority":
                preferences_repo.get_priority(
                    current_user.id
                ),
        }
    except RepositoryError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=str(exc),
        ) from exc


@router.put("/preferences")
def update_training_coach_preferences(
    request: CoachPreferencesUpdate,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    preferences_repo:
        TrainingCoachPreferencesRepository = Depends(
            get_training_coach_preferences_repository
        ),
):
    try:
        item = preferences_repo.upsert(
            user_id=current_user.id,
            priority=request.priority,
            updated_at=datetime.now(
                timezone.utc
            ).isoformat(),
        )

        return {
            "priority": (
                item.get("priority")
                if item
                else request.priority
            ),
        }
    except RepositoryError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=str(exc),
        ) from exc


@router.post("/reconcile")
def reconcile_training_coach(
    request: CoachReconcileRequest,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    activities_repo:
        ActivitiesRepository = Depends(
            get_activities_repository
        ),
    planned_repo:
        PlannedActivitiesRepository = Depends(
            get_planned_activities_repository
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
    adjustment_repo:
        TrainingCoachAdjustmentsRepository = Depends(
            get_training_coach_adjustments_repository
        ),
    preferences_repo:
        TrainingCoachPreferencesRepository = Depends(
            get_training_coach_preferences_repository
        ),
):
    as_of = request.as_of or date.today()

    try:
        priority = preferences_repo.get_priority(
            current_user.id
        )

        context = _coach_context(
            user_id=current_user.id,
            as_of=as_of,
            activities_repo=activities_repo,
            planned_repo=planned_repo,
            workouts_repo=workouts_repo,
            exercises_repo=exercises_repo,
            workout_logs_repo=
                workout_logs_repo,
            set_logs_repo=set_logs_repo,
            priority=priority,
        )

        resolved = []

        for proposal in context["proposals"]:
            existing = (
                adjustment_repo.get_for_signal(
                    user_id=current_user.id,
                    source_kind=
                        proposal["source_kind"],
                    source_id=
                        proposal["source_id"],
                    target_kind=
                        proposal["target_kind"],
                    target_id=
                        proposal["target_id"],
                    action=proposal["action"],
                )
            )

            if existing:
                if (
                    existing.get("decision")
                    == "proposed"
                ):
                    refreshed = (
                        adjustment_repo.update(
                            adjustment_id=
                                existing["id"],
                            user_id=current_user.id,
                            payload={
                                "severity":
                                    proposal[
                                        "severity"
                                    ],
                                "scope":
                                    proposal["scope"],
                                "title":
                                    proposal["title"],
                                "message":
                                    proposal["message"],
                                "proposed_changes":
                                    proposal[
                                        "proposed_changes"
                                    ],
                                "before_state":
                                    proposal.get(
                                        "before_state"
                                    ),
                                "updated_at":
                                    datetime.now(
                                        timezone.utc
                                    ).isoformat(),
                            },
                        )
                    )
                    resolved.append(
                        refreshed or existing
                    )
                else:
                    resolved.append(existing)

                continue

            if proposal.get("auto_apply"):
                target_guard = (
                    adjustment_repo
                    .get_for_target_action(
                        user_id=current_user.id,
                        target_kind=
                            proposal["target_kind"],
                        target_id=
                            proposal["target_id"],
                        action=proposal["action"],
                    )
                )

                if (
                    target_guard
                    and target_guard.get(
                        "decision"
                    )
                    in {
                        "auto_applied",
                        "accepted",
                    }
                ):
                    resolved.append(
                        target_guard
                    )
                    continue

            created = adjustment_repo.create(
                _adjustment_payload(
                    user_id=current_user.id,
                    proposal=proposal,
                )
            )

            if not created:
                raise RepositoryError(
                    "Coach adjustment was "
                    "not persisted"
                )

            if proposal.get("auto_apply"):
                after_state = _apply_adjustment(
                    user_id=current_user.id,
                    adjustment=created,
                    workouts_repo=workouts_repo,
                    exercises_repo=exercises_repo,
                    planned_repo=planned_repo,
                )

                updated = adjustment_repo.update(
                    adjustment_id=
                        created["id"],
                    user_id=current_user.id,
                    payload={
                        "decision":
                            "auto_applied",
                        "after_state":
                            after_state,
                        "updated_at":
                            datetime.now(
                                timezone.utc
                            ).isoformat(),
                    },
                )

                resolved.append(
                    updated or created
                )
            else:
                resolved.append(created)

        history = adjustment_repo.list_recent(
            user_id=current_user.id,
            start_date=(
                as_of - timedelta(days=7)
            ),
            end_date=(
                as_of + timedelta(days=7)
            ),
        )

        return {
            "policy": priority,
            "as_of": context["as_of"],
            "window": {
                "recent_start":
                    context["recent_start"],
                "future_end":
                    context["future_end"],
            },
            "load_events":
                context["events"],
            "recovery_alerts":
                context.get("recovery_alerts", []),
            "adjustments": resolved,
            "history": history,
            "summary": {
                "events":
                    len(context["events"]),
                "proposed": sum(
                    item.get("decision")
                    == "proposed"
                    for item in resolved
                ),
                "auto_applied": sum(
                    item.get("decision")
                    == "auto_applied"
                    for item in resolved
                ),
            },
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


@router.post("/recovery/{kind}/{session_id}/apply")
def apply_skipped_session_recovery(
    kind: Literal["planned_activity", "strength_workout"],
    session_id: str,
    request: CoachRecoveryApplyRequest,
    current_user: CurrentUser = Depends(get_current_user),
    planned_repo: PlannedActivitiesRepository = Depends(
        get_planned_activities_repository
    ),
    workouts_repo: StrengthWorkoutsRepository = Depends(
        get_strength_workouts_repository
    ),
    plans_repo: StrengthPlansRepository = Depends(
        get_strength_plans_repository
    ),
    workout_logs_repo: StrengthWorkoutLogsRepository = Depends(
        get_strength_workout_logs_repository
    ),
    exercises_repo: StrengthWorkoutExercisesRepository = Depends(
        get_strength_workout_exercises_repository
    ),
    set_logs_repo: StrengthSetLogsRepository = Depends(
        get_strength_set_logs_repository
    ),
    activities_repo: ActivitiesRepository = Depends(
        get_activities_repository
    ),
):
    # Recompute a suggestion on the server. The client cannot select
    # an unchecked date or move a different user's session.
    as_of = date.today()
    recent_start = as_of - timedelta(days=3)
    future_end = as_of + timedelta(days=8)

    if kind == "planned_activity":
        source = planned_repo.get(session_id, current_user.id)
        if source and not _is_running_planned(source):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La seduta non è una corsa ripianificabile.",
            )
    else:
        source = workouts_repo.get(current_user.id, session_id)

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seduta non trovata.",
        )
    if (
        source.get("status") != "skipped"
        or str(source.get("scheduled_date")) != request.original_date.isoformat()
        or not (recent_start <= request.original_date <= as_of)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La seduta è cambiata. Aggiorna il Coach.",
        )

    # A skipped final workout may have completed its strength plan.
    # Reactivate only that completed plan when this workout is recovered.
    plan_to_reopen = None
    if kind == "strength_workout" and source.get("strength_plan_id"):
        plan_to_reopen = plans_repo.get(
            source["strength_plan_id"], current_user.id,
        )
        if not plan_to_reopen or plan_to_reopen.get("status") not in {
            "active", "completed"
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Il programma palestra non è più attivo.",
            )

    try:
        context = _coach_context(
            user_id=current_user.id,
            as_of=as_of,
            activities_repo=activities_repo,
            planned_repo=planned_repo,
            workouts_repo=workouts_repo,
            exercises_repo=exercises_repo,
            workout_logs_repo=workout_logs_repo,
            set_logs_repo=set_logs_repo,
        )
        alerts = context["recovery_alerts"]
        match = next(
            (
                item for item in alerts
                if item["kind"] == kind
                and item["session_id"] == session_id
            ),
            None,
        )
        if (
            not match
            or match["suggested_date"] != request.suggested_date.isoformat()
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La proposta non è più valida. Aggiorna il Coach.",
            )

        if kind == "planned_activity":
            updated = planned_repo.reschedule_skipped(
                activity_id=session_id,
                user_id=current_user.id,
                original_date=request.original_date.isoformat(),
                new_date=request.suggested_date.isoformat(),
            )
        else:
            updated = workouts_repo.reschedule_skipped(
                workout_id=session_id,
                user_id=current_user.id,
                original_date=request.original_date.isoformat(),
                new_date=request.suggested_date.isoformat(),
            )

        if not updated:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La seduta è cambiata. Aggiorna il Coach.",
            )

        plan_update = None
        if plan_to_reopen and plan_to_reopen.get("status") == "completed":
            plan_update = plans_repo.update_status(
                plan_id=plan_to_reopen["id"],
                user_id=current_user.id,
                status="active",
            )
            if not plan_update:
                # Two Supabase updates are not atomic. Restore the
                # skipped workout when the plan cannot be reopened.
                undone = workouts_repo.undo_recovery(
                    workout_id=session_id,
                    user_id=current_user.id,
                    original_date=request.original_date.isoformat(),
                    recovered_date=request.suggested_date.isoformat(),
                )
                if not undone:
                    raise RepositoryError(
                        "Strength plan reactivation and recovery "
                        "compensation both failed; manual repair needed"
                    )
                raise RepositoryError(
                    "Strength plan could not be reactivated; "
                    "workout recovery was reverted"
                )

        return {
            "applied": True,
            "item": updated,
            "plan": plan_update,
        }

    except HTTPException:
        raise
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post(
    "/adjustments/{adjustment_id}/apply"
)
def apply_training_coach_adjustment(
    adjustment_id: str,
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
    planned_repo:
        PlannedActivitiesRepository = Depends(
            get_planned_activities_repository
        ),
    adjustment_repo:
        TrainingCoachAdjustmentsRepository = Depends(
            get_training_coach_adjustments_repository
        ),
):
    try:
        adjustment = adjustment_repo.get(
            adjustment_id,
            current_user.id,
        )

        if not adjustment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proposta Coach non trovata.",
            )

        if adjustment.get("decision") != "proposed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Questa proposta Coach è "
                    "già stata gestita."
                ),
            )

        after_state = _apply_adjustment(
            user_id=current_user.id,
            adjustment=adjustment,
            workouts_repo=workouts_repo,
            exercises_repo=exercises_repo,
            planned_repo=planned_repo,
        )

        updated = adjustment_repo.update(
            adjustment_id=adjustment_id,
            user_id=current_user.id,
            payload={
                "decision": "accepted",
                "after_state": after_state,
                "updated_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            },
        )

        return {
            "applied": True,
            "adjustment": updated,
            "after_state": after_state,
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
    "/adjustments/{adjustment_id}/dismiss"
)
def dismiss_training_coach_adjustment(
    adjustment_id: str,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    adjustment_repo:
        TrainingCoachAdjustmentsRepository = Depends(
            get_training_coach_adjustments_repository
        ),
):
    try:
        adjustment = adjustment_repo.get(
            adjustment_id,
            current_user.id,
        )

        if not adjustment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proposta Coach non trovata.",
            )

        if adjustment.get("decision") != "proposed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Questa proposta Coach è "
                    "già stata gestita."
                ),
            )

        updated = adjustment_repo.update(
            adjustment_id=adjustment_id,
            user_id=current_user.id,
            payload={
                "decision": "dismissed",
                "updated_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            },
        )

        return {
            "dismissed": True,
            "adjustment": updated,
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


@router.get("/adjustments")
def list_training_coach_adjustments(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    adjustment_repo:
        TrainingCoachAdjustmentsRepository = Depends(
            get_training_coach_adjustments_repository
        ),
):
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Intervallo Coach non valido.",
        )

    if (end_date - start_date).days > 60:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Intervallo Coach troppo ampio.",
        )

    try:
        items = adjustment_repo.list_recent(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
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
