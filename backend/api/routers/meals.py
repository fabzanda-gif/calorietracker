from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.dependencies import get_meals_repository
from backend.repositories.base import RepositoryError
from backend.repositories.meals import MealsRepository


router = APIRouter(
    prefix="/meals",
    tags=["meals"],
)


@router.get("/{meal_date}")
def get_meals_for_date(
    meal_date: date,
    user_id: str = Query(
        ...,
        min_length=1,
        description=(
            "TEMPORARY development parameter. "
            "It will be replaced by authenticated-user resolution."
        ),
    ),
    repo: MealsRepository = Depends(get_meals_repository),
):
    """
    First real SanoSync API endpoint.

    Development only:
    `user_id` is explicit for now so we can verify repository/API wiring
    before migrating authentication.
    """
    try:
        meals = repo.list_for_date_compatible(
            user_id=user_id,
            log_date=meal_date,
        )
        return {
            "date": str(meal_date),
            "count": len(meals),
            "items": meals,
        }
    except RepositoryError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc
