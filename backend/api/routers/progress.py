from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_meals_repository,
    get_weight_repository,
)
from backend.repositories.activities import ActivitiesRepository
from backend.repositories.base import RepositoryError
from backend.repositories.meals import MealsRepository
from backend.repositories.weight import WeightRepository
from backend.services.progress_nutrition import ProgressNutritionService


router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/nutrition")
def get_nutrition_progress(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: CurrentUser = Depends(get_current_user),
    meals_repo: MealsRepository = Depends(get_meals_repository),
    activities_repo: ActivitiesRepository = Depends(
        get_activities_repository
    ),
    weight_repo: WeightRepository = Depends(
        get_weight_repository
    ),
):
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be on or after start_date",
        )

    if (end_date - start_date).days > 366:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum progress range is 367 days",
        )

    try:
        latest_weight = weight_repo.latest(current_user.id)

        current_weight = (
            latest_weight.get("weight")
            if latest_weight is not None
            else None
        )

        return ProgressNutritionService(
            meals_repo=meals_repo,
            activities_repo=activities_repo,
        ).build(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            metadata=current_user.metadata,
            current_weight=current_weight,
        )

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
