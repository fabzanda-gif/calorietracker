from __future__ import annotations

from datetime import date as Date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.api.dependencies import CurrentUser, get_current_user
from backend.repositories.base import RepositoryError
from backend.repositories.daily_logs import DailyLogsRepository


router = APIRouter(
    prefix="/daily-logs",
    tags=["daily-logs"],
)


class DailyLogUpdate(BaseModel):
    weight: float | None = None
    steps: int | None = None
    day_type: str | None = None
    activity_plan: str | None = None


def get_daily_logs_repository(
    current_user: CurrentUser = Depends(get_current_user),
) -> DailyLogsRepository:
    """
    Create an authenticated Supabase client for daily-log queries.
    """
    from backend.api.dependencies import _supabase_settings
    from supabase import create_client

    url, key = _supabase_settings()
    client = create_client(url, key)
    client.postgrest.auth(current_user.access_token)

    return DailyLogsRepository(client)


@router.get("/{log_date}")
def get_daily_log(
    log_date: Date,
    current_user: CurrentUser = Depends(get_current_user),
    repo: DailyLogsRepository = Depends(get_daily_logs_repository),
):
    try:
        item = repo.get_for_date_compatible(
            user_id=current_user.id,
            log_date=log_date,
        )

        return {
            "date": str(log_date),
            "item": item,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.patch("/{log_date}")
def update_daily_log(
    log_date: Date,
    changes: DailyLogUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    repo: DailyLogsRepository = Depends(get_daily_logs_repository),
):
    payload = changes.model_dump(exclude_unset=True)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields supplied",
        )

    # Basic input validation kept here to avoid writing obviously invalid
    # values while preserving the current Streamlit behaviour.
    if "steps" in payload and payload["steps"] is not None:
        if payload["steps"] < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Steps cannot be negative",
            )

    if "weight" in payload and payload["weight"] is not None:
        if payload["weight"] <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Weight must be greater than zero",
            )

    try:
        item = repo.upsert_for_date(
            user_id=current_user.id,
            log_date=log_date,
            values=payload,
        )

        return {
            "updated": True,
            "date": str(log_date),
            "item": item,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("")
def get_daily_logs_range(
    start_date: Date,
    end_date: Date,
    current_user: CurrentUser = Depends(get_current_user),
    repo: DailyLogsRepository = Depends(get_daily_logs_repository),
):
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be on or after start_date",
        )

    try:
        items = repo.list_date_range(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
        )

        return {
            "start_date": str(start_date),
            "end_date": str(end_date),
            "count": len(items),
            "items": items,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
