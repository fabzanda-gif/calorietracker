from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_daily_logs_repository,
)
from backend.repositories.activities import ActivitiesRepository
from backend.repositories.base import RepositoryError
from backend.repositories.daily_logs import DailyLogsRepository
from backend.services.day_history import DayHistoryService


router = APIRouter(
    prefix="/day-history",
    tags=["day-history"],
)


@router.get("/activity-profile")
def get_activity_profile(
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    daily_logs_repo: DailyLogsRepository = Depends(
        get_daily_logs_repository
    ),
    activities_repo: ActivitiesRepository = Depends(
        get_activities_repository
    ),
):
    try:
        return DayHistoryService(
            daily_logs_repo=daily_logs_repo,
            activities_repo=activities_repo,
        ).activity_profile_by_day_type(
            user_id=current_user.id,
        )

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
