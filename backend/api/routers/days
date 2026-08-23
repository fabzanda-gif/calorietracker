from __future__ import annotations

from datetime import date as Date

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_daily_logs_repository,
)
from backend.repositories.base import RepositoryError
from backend.repositories.daily_logs import DailyLogsRepository
from backend.services.day import DayService


router = APIRouter(prefix="/days", tags=["days"])


@router.get("/{day_date}")
def get_day(
    day_date: Date,
    current_user: CurrentUser = Depends(get_current_user),
    repo: DailyLogsRepository = Depends(get_daily_logs_repository),
):
    try:
        service = DayService(repo)
        return service.build_day(
            user_id=current_user.id,
            day_date=day_date,
        )
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
