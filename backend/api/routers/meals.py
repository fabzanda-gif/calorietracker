from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies import CurrentUser, get_current_user, get_meals_repository
from backend.repositories.base import RepositoryError
from backend.repositories.meals import MealsRepository


router = APIRouter(prefix="/meals", tags=["meals"])


@router.get("/{meal_date}")
def get_meals_for_date(
    meal_date: date,
    current_user: CurrentUser = Depends(get_current_user),
    repo: MealsRepository = Depends(get_meals_repository),
):
    try:
        meals = repo.list_for_date_compatible(
            user_id=current_user.id,
            log_date=meal_date,
        )
        return {
            "date": str(meal_date),
            "count": len(meals),
            "items": meals,
        }
    except RepositoryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
