from __future__ import annotations

import base64
import binascii
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_daily_logs_repository,
)
from backend.repositories.activities import ActivitiesRepository
from backend.repositories.base import RepositoryError
from backend.repositories.daily_logs import DailyLogsRepository
from backend.services.gpx_activity import (
    GpxActivityError,
    parse_gpx_activity,
)
from backend.services.activity_movement import (
    estimated_activity_steps,
    normalize_activity_type,
)
from backend.services.activity_movement_sync import (
    ActivityMovementSyncService,
)


router = APIRouter(prefix="/activities", tags=["activities"])


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
    burned_calories: int = Field(default=0, ge=0)


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
        rows = repo.list_date_range(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
        )

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

    payload = {
        "user_id": current_user.id,
        "date": str(effective_date),
        "activity_name": activity_name,
        "activity_type": (
            request.activity_type.strip()
            if request.activity_type
            else None
        ),
        "burned_calories": request.burned_calories,
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
        rows = repo.list_for_date(current_user.id, activity_date)
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
