from __future__ import annotations

import base64
import binascii
from datetime import date, time, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_daily_logs_repository,
    get_meals_repository,
    get_planned_activities_repository,
    get_training_plans_repository,
    get_weight_repository,
)
from backend.repositories.activities import ActivitiesRepository
from backend.repositories.base import RepositoryError
from backend.repositories.daily_logs import DailyLogsRepository
from backend.repositories.meals import MealsRepository
from backend.repositories.planned_activities import (
    PlannedActivitiesRepository,
)
from backend.repositories.training_plans import (
    TrainingPlansRepository,
)
from backend.repositories.weight import WeightRepository
from backend.services.gpx_activity import (
    GpxActivityError,
    parse_gpx_activity,
)
from backend.services.activity_movement import (
    estimated_activity_steps,
    estimated_gpx_calories,
    normalize_activity_type,
)
from backend.services.activity_movement_sync import (
    ActivityMovementSyncService,
)
from backend.services.activity_comment import (
    ActivityCommentError,
    ActivityCommentService,
    fallback_activity_comment,
)
from backend.services.profile_goal import ProfileGoalService
from backend.services.running_plan import (
    RunningPlanInput,
    build_running_plan,
)


router = APIRouter(prefix="/activities", tags=["activities"])


def _is_training_activity(activity: dict) -> bool:
    if activity.get("source") == "gpx":
        return True
    name = str(activity.get("activity_name") or "").strip().casefold()
    return not any(
        name == prefix or name.startswith(f"{prefix} ") or name.startswith(f"{prefix} (")
        for prefix in ("passi", "steps")
    )


def _with_activity_defaults(activity: dict) -> dict:
    """Fill safe display defaults for legacy rows without changing storage."""
    item = dict(activity)
    activity_type = normalize_activity_type(
        item.get("activity_type") or item.get("activity_name")
    )
    item["activity_type"] = activity_type

    if activity_type == "Padel" and not item.get("duration_seconds"):
        item["duration_seconds"] = 90 * 60

    return item


class ActivityCreate(BaseModel):
    date: date
    activity_name: str = Field(min_length=1)
    burned_calories: int = Field(ge=0)
    activity_type: str | None = Field(
        default=None,
        max_length=80,
    )
    duration_seconds: int | None = Field(
        default=None,
        ge=0,
    )


class ActivityUpdate(BaseModel):
    activity_name: str | None = None
    burned_calories: int | None = Field(default=None, ge=0)


class ActivityCommentRequest(BaseModel):
    activity_name: str = Field(
        min_length=1,
        max_length=160,
    )
    activity_type: str | None = Field(
        default=None,
        max_length=80,
    )
    burned_calories: int = Field(
        default=0,
        ge=0,
    )
    duration_seconds: int | None = Field(
        default=None,
        ge=0,
    )
    distance_meters: float | None = Field(
        default=None,
        ge=0,
    )
    average_cadence: float | None = Field(
        default=None,
        ge=0,
    )
    average_heart_rate: float | None = Field(
        default=None,
        ge=0,
    )
    source: str | None = Field(
        default=None,
        max_length=40,
    )
    mode: str = Field(
        default="standard",
        pattern="^(standard|zero)$",
    )


class PlannedActivityCreate(BaseModel):
    scheduled_date: date
    scheduled_time: time | None = None

    title: str = Field(
        min_length=1,
        max_length=160,
    )
    activity_type: str = Field(
        min_length=1,
        max_length=80,
    )

    duration_minutes: int | None = Field(
        default=None,
        gt=0,
    )
    distance_meters: float | None = Field(
        default=None,
        ge=0,
    )

    intensity: str = Field(
        default="moderate",
        pattern="^(low|moderate|hard|race|unknown)$",
    )

    notes: str | None = Field(
        default=None,
        max_length=2000,
    )


class PlannedActivityUpdate(BaseModel):
    scheduled_date: date | None = None
    scheduled_time: time | None = None

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=160,
    )
    activity_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=80,
    )

    duration_minutes: int | None = Field(
        default=None,
        gt=0,
    )
    distance_meters: float | None = Field(
        default=None,
        ge=0,
    )

    intensity: str | None = Field(
        default=None,
        pattern="^(low|moderate|hard|race|unknown)$",
    )

    notes: str | None = Field(
        default=None,
        max_length=2000,
    )

    status: str | None = Field(
        default=None,
        pattern="^(planned|completed|skipped)$",
    )


class RunningTrainingPlanCreate(BaseModel):
    start_date: date
    target_date: date

    current_distance_meters: float = Field(
        gt=0,
    )
    current_pace_seconds_per_km: int = Field(
        gt=0,
    )

    target_distance_meters: float = Field(
        gt=0,
    )
    target_pace_seconds_per_km: int = Field(
        gt=0,
    )

    sessions_per_week: int = Field(
        ge=2,
        le=5,
    )

    long_run_weekday: int = Field(
        default=6,
        ge=0,
        le=6,
    )

    replace_active: bool = False


class GpxPreviewRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)
    activity_type: str | None = Field(default="Corsa", max_length=80)


class GpxImportRequest(GpxPreviewRequest):
    activity_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=160,
    )
    activity_type: str | None = Field(
        default=None,
        max_length=80,
    )
    activity_date: date | None = None
    burned_calories: int | None = Field(default=None, ge=0)


@router.get("/training-plans")
def list_training_plans(
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: TrainingPlansRepository = Depends(
        get_training_plans_repository
    ),
):
    try:
        items = repo.list_for_user(
            current_user.id
        )
        return {
            "count": len(items),
            "items": items,
        }
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get(
    "/training-plans/{plan_id}/sessions"
)
def list_training_plan_sessions(
    plan_id: str,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: PlannedActivitiesRepository = Depends(
        get_planned_activities_repository
    ),
):
    try:
        items = repo.list_for_training_plan(
            current_user.id,
            plan_id,
        )

        return {
            "count": len(items),
            "items": items,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.delete("/training-plans/{plan_id}")
def delete_training_plan(
    plan_id: str,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: TrainingPlansRepository = Depends(
        get_training_plans_repository
    ),
):
    try:
        repo.delete(
            plan_id,
            current_user.id,
        )

        return {
            "deleted": True,
            "id": plan_id,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post(
    "/training-plans/running/preview",
)
def preview_running_training_plan(
    request: RunningTrainingPlanCreate,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
):
    # Authentication is still required, but this
    # endpoint intentionally performs no persistence.
    _ = current_user

    total_days = (
        request.target_date -
        request.start_date
    ).days

    if total_days < 56:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Il piano deve durare almeno 8 settimane."
            ),
        )

    try:
        sessions = build_running_plan(
            RunningPlanInput(
                start_date=request.start_date,
                target_date=request.target_date,
                current_distance_meters=(
                    request.current_distance_meters
                ),
                current_pace_seconds_per_km=(
                    request.current_pace_seconds_per_km
                ),
                target_distance_meters=(
                    request.target_distance_meters
                ),
                target_pace_seconds_per_km=(
                    request.target_pace_seconds_per_km
                ),
                sessions_per_week=(
                    request.sessions_per_week
                ),
                long_run_weekday=(
                    request.long_run_weekday
                ),
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    total_weeks = max(
        item["training_week"]
        for item in sessions
    )

    return {
        "preview": True,
        "total_weeks": total_weeks,
        "session_count": len(sessions),
        "sessions": sessions,
    }


@router.post(
    "/training-plans/running",
    status_code=status.HTTP_201_CREATED,
)
def create_running_training_plan(
    request: RunningTrainingPlanCreate,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    plans_repo: TrainingPlansRepository = Depends(
        get_training_plans_repository
    ),
    planned_repo: PlannedActivitiesRepository = Depends(
        get_planned_activities_repository
    ),
):
    total_days = (
        request.target_date -
        request.start_date
    ).days

    if total_days < 56:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Il piano deve durare almeno 8 settimane."
            ),
        )

    try:
        sessions = build_running_plan(
            RunningPlanInput(
                start_date=request.start_date,
                target_date=request.target_date,
                current_distance_meters=(
                    request.current_distance_meters
                ),
                current_pace_seconds_per_km=(
                    request.current_pace_seconds_per_km
                ),
                target_distance_meters=(
                    request.target_distance_meters
                ),
                target_pace_seconds_per_km=(
                    request.target_pace_seconds_per_km
                ),
                sessions_per_week=(
                    request.sessions_per_week
                ),
                long_run_weekday=(
                    request.long_run_weekday
                ),
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    total_weeks = max(
        item["training_week"]
        for item in sessions
    )

    try:
        existing_plans = (
            plans_repo.list_for_user(
                current_user.id
            )
        )
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    active_plans = [
        item
        for item in existing_plans
        if (
            item.get("sport") == "running"
            and item.get("status") == "active"
        )
    ]

    if (
        active_plans
        and not request.replace_active
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Hai già un piano di corsa attivo. "
                "Conferma la sostituzione per crearne uno nuovo."
            ),
        )

    plan_payload = {
        "user_id": current_user.id,
        "sport": "running",
        "start_date": str(request.start_date),
        "target_date": str(request.target_date),
        "current_distance_meters":
            request.current_distance_meters,
        "current_pace_seconds_per_km":
            request.current_pace_seconds_per_km,
        "target_distance_meters":
            request.target_distance_meters,
        "target_pace_seconds_per_km":
            request.target_pace_seconds_per_km,
        "sessions_per_week":
            request.sessions_per_week,
        "long_run_weekday":
            request.long_run_weekday,
        "total_weeks": total_weeks,
        "status": "active",
    }

    plan = None

    try:
        plan = plans_repo.create(
            plan_payload
        )

        if not plan or not plan.get("id"):
            raise RepositoryError(
                "Training plan was not persisted"
            )

        plan_id = plan["id"]

        activity_payloads = []

        for session in sessions:
            activity_payloads.append(
                {
                    **session,
                    "user_id": current_user.id,
                    "training_plan_id": plan_id,
                }
            )

        created_sessions = (
            planned_repo.create_many(
                activity_payloads
            )
        )

        replaced_plan_ids = []

        if request.replace_active:
            for existing_plan in active_plans:
                existing_id = (
                    existing_plan.get("id")
                )

                if (
                    not existing_id
                    or existing_id == plan_id
                ):
                    continue

                plans_repo.delete(
                    existing_id,
                    current_user.id,
                )

                replaced_plan_ids.append(
                    existing_id
                )

        return {
            "created": True,
            "plan": plan,
            "session_count":
                len(created_sessions),
            "sessions":
                created_sessions,
            "replaced_plan_ids":
                replaced_plan_ids,
        }

    except RepositoryError as exc:
        if plan and plan.get("id"):
            try:
                plans_repo.delete(
                    plan["id"],
                    current_user.id,
                )
            except RepositoryError:
                pass

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/planned")
def list_planned_activities(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: PlannedActivitiesRepository = Depends(
        get_planned_activities_repository
    ),
):
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid planned activity date range",
        )

    if (end_date - start_date).days > 366:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Planned activity range is too large",
        )

    try:
        items = repo.list_range(
            current_user.id,
            start_date,
            end_date,
        )
        return {
            "count": len(items),
            "items": items,
        }
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post(
    "/planned",
    status_code=status.HTTP_201_CREATED,
)
def create_planned_activity(
    request: PlannedActivityCreate,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: PlannedActivitiesRepository = Depends(
        get_planned_activities_repository
    ),
):
    payload = request.model_dump(
        mode="json"
    )
    payload["user_id"] = current_user.id
    payload["title"] = payload["title"].strip()
    payload["activity_type"] = (
        payload["activity_type"].strip()
    )

    if payload.get("notes"):
        payload["notes"] = (
            payload["notes"].strip() or None
        )

    try:
        item = repo.create(payload)
        return {
            "created": True,
            "item": item or payload,
        }
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.patch("/planned/{planned_id}")
def update_planned_activity(
    planned_id: str,
    request: PlannedActivityUpdate,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: PlannedActivitiesRepository = Depends(
        get_planned_activities_repository
    ),
):
    payload = request.model_dump(
        exclude_unset=True,
        mode="json",
    )

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields supplied",
        )

    if "title" in payload:
        payload["title"] = payload["title"].strip()

    if "activity_type" in payload:
        payload["activity_type"] = (
            payload["activity_type"].strip()
        )

    if "notes" in payload and payload["notes"]:
        payload["notes"] = (
            payload["notes"].strip() or None
        )

    try:
        item = repo.update(
            planned_id,
            current_user.id,
            payload,
        )

        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Planned activity not found",
            )

        return {
            "updated": True,
            "item": item,
        }
    except HTTPException:
        raise
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.delete("/planned/{planned_id}")
def delete_planned_activity(
    planned_id: str,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: PlannedActivitiesRepository = Depends(
        get_planned_activities_repository
    ),
):
    try:
        repo.delete(
            planned_id,
            current_user.id,
        )
        return {
            "deleted": True,
            "id": planned_id,
        }
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/overview")
def get_activity_overview(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: CurrentUser = Depends(get_current_user),
    repo: ActivitiesRepository = Depends(get_activities_repository),
    meals_repo: MealsRepository = Depends(get_meals_repository),
    weight_repo: WeightRepository = Depends(get_weight_repository),
):
    if end_date < start_date or (end_date - start_date).days > 62:
        raise HTTPException(status_code=400, detail="Invalid overview date range")

    try:
        activities = [
            _with_activity_defaults(item)
            for item in repo.list_date_range(current_user.id, start_date, end_date)
        ]
        meals = meals_repo.list_date_range(
            current_user.id, start_date, end_date,
            columns="date,calories",
        )
        latest_weight = weight_repo.latest(current_user.id)
        profile = ProfileGoalService().build(
            current_user.metadata,
            current_weight=(latest_weight or {}).get("weight"),
            on_date=end_date,
        )
    except RepositoryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    training = [item for item in activities if _is_training_activity(item)]
    calories_by_date: dict[str, float] = {}
    for meal in meals:
        key = str(meal.get("date") or "")
        calories_by_date[key] = calories_by_date.get(key, 0) + float(meal.get("calories") or 0)
    activity_by_date: dict[str, float] = {}
    for item in training:
        key = str(item.get("date") or "")
        activity_by_date[key] = activity_by_date.get(key, 0) + float(item.get("burned_calories") or 0)

    energy_days = []
    bmr = float(profile.get("bmr") or 0)
    if bmr > 0:
        cursor = start_date
        while cursor <= min(end_date, date.today()):
            key = str(cursor)
            if key in calories_by_date:
                maintenance = bmr * 1.2 + activity_by_date.get(key, 0)
                balance = round(calories_by_date[key] - maintenance)
                state = "maintenance" if abs(balance) <= 100 else ("surplus" if balance > 0 else "deficit")
                energy_days.append({"date": key, "state": state, "balance_kcal": balance})
            cursor += timedelta(days=1)

    return {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "count": len(activities),
        "items": activities,
        "energy_days": energy_days,
        "summary": {
            "workouts": len(training),
            "duration_seconds": sum(int(item.get("duration_seconds") or 0) for item in training),
            "distance_meters": sum(float(item.get("distance_meters") or 0) for item in training),
            "burned_calories": sum(int(item.get("burned_calories") or 0) for item in training),
        },
    }


@router.get("/range")
def get_activities_for_range(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: CurrentUser = Depends(get_current_user),
    repo: ActivitiesRepository = Depends(get_activities_repository),
):
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be on or after start_date",
        )

    try:
        rows = [
            _with_activity_defaults(item)
            for item in repo.list_date_range(
                user_id=current_user.id,
                start_date=start_date,
                end_date=end_date,
            )
        ]

        return {
            "start_date": str(start_date),
            "end_date": str(end_date),
            "count": len(rows),
            "items": rows,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("/gpx/preview")
def preview_gpx_activity(
    request: GpxPreviewRequest,
    current_user: CurrentUser = Depends(get_current_user),
    weight_repo: WeightRepository = Depends(get_weight_repository),
):
    try:
        content = base64.b64decode(
            request.content_base64,
            validate=True,
        )
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Il contenuto del file non è valido.",
        ) from exc

    fallback_name = (
        Path(request.file_name).stem.strip()
        or "Attività GPX"
    )

    try:
        preview = parse_gpx_activity(
            content,
            fallback_name=fallback_name,
        )
    except GpxActivityError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    latest_weight = weight_repo.latest(current_user.id)
    preview["estimated_calories"] = estimated_gpx_calories(
        activity_type=request.activity_type or preview["activity_name"],
        duration_seconds=preview["duration_seconds"],
        distance_meters=preview["distance_meters"],
        weight_kg=(latest_weight or {}).get("weight"),
    )

    return {
        "preview": preview,
        "file_name": request.file_name,
    }


@router.post(
    "/gpx/import",
    status_code=status.HTTP_201_CREATED,
)
def import_gpx_activity(
    request: GpxImportRequest,
    current_user: CurrentUser = Depends(get_current_user),
    repo: ActivitiesRepository = Depends(
        get_activities_repository
    ),
    daily_logs_repo: DailyLogsRepository = Depends(
        get_daily_logs_repository
    ),
    weight_repo: WeightRepository = Depends(get_weight_repository),
):
    try:
        content = base64.b64decode(
            request.content_base64,
            validate=True,
        )
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Il contenuto del file non è valido.",
        ) from exc

    fallback_name = (
        Path(request.file_name).stem.strip()
        or "Attività GPX"
    )

    try:
        parsed = parse_gpx_activity(
            content,
            fallback_name=fallback_name,
        )
    except GpxActivityError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    effective_date = (
        request.activity_date
        or parsed.get("date")
    )

    if effective_date is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Il GPX non contiene una data. "
                "Seleziona manualmente il giorno "
                "dell'attività."
            ),
        )

    activity_name = (
        request.activity_name.strip()
        if request.activity_name
        else parsed["activity_name"]
    )

    latest_weight = weight_repo.latest(current_user.id)
    burned_calories = request.burned_calories
    if burned_calories is None:
        burned_calories = estimated_gpx_calories(
            activity_type=request.activity_type or parsed["activity_name"],
            duration_seconds=parsed["duration_seconds"],
            distance_meters=parsed["distance_meters"],
            weight_kg=(latest_weight or {}).get("weight"),
        )

    payload = {
        "user_id": current_user.id,
        "date": str(effective_date),
        "activity_name": activity_name,
        "activity_type": (
            request.activity_type.strip()
            if request.activity_type
            else None
        ),
        "burned_calories": burned_calories,
        "source": "gpx",
        "started_at": parsed["started_at"],
        "duration_seconds": parsed[
            "duration_seconds"
        ],
        "distance_meters": parsed[
            "distance_meters"
        ],
        "average_cadence": parsed[
            "average_cadence"
        ],
        "average_heart_rate": parsed[
            "average_heart_rate"
        ],
        "route_points": parsed["route_points"],
        "series_points": parsed["series_points"],
        "original_point_count": parsed[
            "original_point_count"
        ],
        "estimated_steps": estimated_activity_steps(
            activity_type=(
                request.activity_type
                or parsed["activity_name"]
            ),
            duration_seconds=parsed[
                "duration_seconds"
            ],
            average_cadence=parsed[
                "average_cadence"
            ],
        ),
        "gpx_file_name": request.file_name,
    }

    try:
        item = repo.create(payload)

        movement = ActivityMovementSyncService(
            activities_repo=repo,
            daily_logs_repo=daily_logs_repo,
        ).sync(
            user_id=current_user.id,
            day_date=payload["date"],
        )

        return {
            "created": True,
            "item": (
                item
                if item is not None
                else payload
            ),
            "movement": movement,
        }
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("/comment")
def get_activity_comment(
    request: ActivityCommentRequest,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
):
    # current_user is intentionally resolved here:
    # generating AI text remains an authenticated
    # SanoSync capability.
    _ = current_user

    payload = request.model_dump(
        exclude={"mode"}
    )

    mode = (
        "zero"
        if request.mode == "zero"
        else "standard"
    )

    try:
        comment = (
            ActivityCommentService()
            .generate(
                payload,
                mode=mode,
            )
        )

        return {
            "comment": comment,
            "source": "groq",
            "mode": mode,
        }

    except ActivityCommentError:
        return {
            "comment": fallback_activity_comment(
                payload,
                mode=mode,
            ),
            "source": "fallback",
            "mode": mode,
        }


@router.get("/movement/{activity_date}")
def get_activity_movement(
    activity_date: date,
    current_user: CurrentUser = Depends(get_current_user),
    repo: ActivitiesRepository = Depends(
        get_activities_repository
    ),
    daily_logs_repo: DailyLogsRepository = Depends(
        get_daily_logs_repository
    ),
):
    try:
        return ActivityMovementSyncService(
            activities_repo=repo,
            daily_logs_repo=daily_logs_repo,
        ).sync(
            user_id=current_user.id,
            day_date=activity_date,
        )
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/{activity_date}")
def get_activities_for_date(
    activity_date: date,
    current_user: CurrentUser = Depends(get_current_user),
    repo: ActivitiesRepository = Depends(get_activities_repository),
):
    try:
        rows = [
            _with_activity_defaults(item)
            for item in repo.list_for_date(current_user.id, activity_date)
        ]
        return {
            "date": str(activity_date),
            "count": len(rows),
            "items": rows,
        }
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("", status_code=status.HTTP_201_CREATED)
def create_activity(
    activity: ActivityCreate,
    current_user: CurrentUser = Depends(get_current_user),
    repo: ActivitiesRepository = Depends(
        get_activities_repository
    ),
    daily_logs_repo: DailyLogsRepository = Depends(
        get_daily_logs_repository
    ),
):
    payload = activity.model_dump()
    payload["date"] = str(payload["date"])
    payload["user_id"] = current_user.id

    if (
        payload.get("activity_type")
        or payload.get("duration_seconds")
    ):
        activity_type = normalize_activity_type(
            payload.get("activity_type")
            or payload["activity_name"]
        )
        payload["activity_type"] = activity_type
        payload["estimated_steps"] = (
            estimated_activity_steps(
                activity_type=activity_type,
                duration_seconds=payload.get(
                    "duration_seconds"
                ),
            )
        )

    try:
        item = repo.create(payload)

        movement = ActivityMovementSyncService(
            activities_repo=repo,
            daily_logs_repo=daily_logs_repo,
        ).sync(
            user_id=current_user.id,
            day_date=payload["date"],
        )

        return {
            "created": True,
            "item": item if item is not None else payload,
            "movement": movement,
        }
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.patch("/{activity_id}")
def update_activity(
    activity_id: str,
    changes: ActivityUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    repo: ActivitiesRepository = Depends(get_activities_repository),
):
    payload = changes.model_dump(exclude_unset=True)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields supplied",
        )

    try:
        item = repo.update(
            activity_id=activity_id,
            user_id=current_user.id,
            payload=payload,
        )
        return {"updated": True, "item": item}
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.delete("/{activity_id}")
def delete_activity(
    activity_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repo: ActivitiesRepository = Depends(get_activities_repository),
):
    try:
        repo.delete(activity_id=activity_id, user_id=current_user.id)
        return {"deleted": True, "id": activity_id}
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
