from __future__ import annotations

from datetime import date as Date

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_daily_logs_repository,
    get_meals_repository,
)
from backend.repositories.base import RepositoryError
from backend.repositories.daily_logs import DailyLogsRepository
from backend.repositories.meals import MealsRepository
from backend.services.insight_presentation import InsightPresentationService
from backend.services.learned_insights import LearnedInsightsService


router = APIRouter(
    prefix="/insights",
    tags=["insights"],
)


@router.get("/learned")
def get_learned_insights(
    on_date: Date | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    daily_logs_repo: DailyLogsRepository = Depends(
        get_daily_logs_repository
    ),
    meals_repo: MealsRepository = Depends(
        get_meals_repository
    ),
):
    """
    Return both structured learned-pattern data and UI-ready presentation cards.
    """
    target_date = on_date or Date.today()

    try:
        structured = LearnedInsightsService(
            daily_logs_repo=daily_logs_repo,
            meals_repo=meals_repo,
        ).build(
            user_id=current_user.id,
            on_date=target_date,
        )

        presentation = InsightPresentationService().present(
            structured
        )

        return {
            **structured,
            "presentation": presentation,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
