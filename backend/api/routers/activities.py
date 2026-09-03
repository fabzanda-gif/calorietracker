from __future__ import annotations

import base64
import binascii
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_daily_logs_repository,
    get_meals_repository,
    get_weight_repository,
)
from backend.repositories.activities import ActivitiesRepository
from backend.repositories.base import RepositoryError
from backend.repositories.daily_logs import DailyLogsRepository
from backend.repositories.meals import MealsRepository
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
from backend.services.profile_goal import ProfileGoalService


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
