from __future__ import annotations

from datetime import date as Date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_decision_selections_repository,
    get_meals_repository,
)
from backend.repositories.base import RepositoryError
from backend.repositories.decision_selections import (
    DecisionSelectionsRepository,
)
from backend.repositories.meals import MealsRepository
from backend.services.decision_outcome_report import (
    DecisionOutcomeReportService,
)


router = APIRouter(
    prefix="/insights",
    tags=["decision-outcomes"],
)


@router.get("/decision-outcomes")
def get_decision_outcomes(
    days: int = Query(default=30, ge=1, le=180),
    current_user: CurrentUser = Depends(get_current_user),
    selections_repo: DecisionSelectionsRepository = Depends(
        get_decision_selections_repository
    ),
    meals_repo: MealsRepository = Depends(
        get_meals_repository
    ),
):
    end_date = Date.today()
    start_date = end_date - timedelta(
        days=days - 1
    )

    try:
        selections = selections_repo.list_date_range(
            current_user.id,
            start_date,
            end_date,
        )

        meals = meals_repo.list_date_range(
            current_user.id,
            start_date,
            end_date,
        )

        report = DecisionOutcomeReportService().build(
            selections=selections,
            meals=meals,
        )

        return {
            "user_id": current_user.id,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "days": days,
            **report,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
