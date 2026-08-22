from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_meals_repository,
)
from backend.repositories.base import RepositoryError
from backend.repositories.meals import MealsRepository


router = APIRouter(prefix="/meals", tags=["meals"])


class MealCreate(BaseModel):
    date: date
    meal_type: str = Field(min_length=1)
    name: str = Field(min_length=1)

    calories: float = 0
    protein: float = 0
    carbs: float = 0
    fat: float = 0

    base_name: str | None = None
    quantity: float | None = None
    is_per_100g: bool | None = None

    base_calories: float | None = None
    base_protein: float | None = None
    base_carbs: float | None = None
    base_fat: float | None = None

    notes: str | None = None
    category: str | None = None
    ingredients_json: Any | None = None
    recipe_servings: float | None = None
    is_shared: bool | None = None
    image_url: str | None = None


class MealUpdate(BaseModel):
    meal_type: str | None = None
    name: str | None = None

    calories: float | None = None
    protein: float | None = None
    carbs: float | None = None
    fat: float | None = None

    base_name: str | None = None
    quantity: float | None = None
    is_per_100g: bool | None = None

    base_calories: float | None = None
    base_protein: float | None = None
    base_carbs: float | None = None
    base_fat: float | None = None

    notes: str | None = None
    category: str | None = None
    ingredients_json: Any | None = None
    recipe_servings: float | None = None
    is_shared: bool | None = None
    image_url: str | None = None


# ------------------------------------------------------------------
# Historical/list endpoints.
# IMPORTANT: keep these BEFORE /{meal_date}, otherwise strings such as
# "history" or "range" could be interpreted as the dynamic date route.
# ------------------------------------------------------------------

@router.get("/history")
def get_meal_history(
    current_user: CurrentUser = Depends(get_current_user),
    repo: MealsRepository = Depends(get_meals_repository),
):
    try:
        meals = repo.list_history_compatible(current_user.id)

        return {
            "count": len(meals),
            "items": meals,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/range")
def get_meals_for_range(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: CurrentUser = Depends(get_current_user),
    repo: MealsRepository = Depends(get_meals_repository),
):
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be on or after start_date",
        )

    try:
        meals = repo.list_date_range(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            columns=(
                "id,date,meal_type,name,base_name,quantity,is_per_100g,"
                "base_calories,base_protein,base_carbs,base_fat,"
                "calories,protein,carbs,fat,notes,category,"
                "ingredients_json,recipe_servings,is_shared,image_url"
            ),
        )

        return {
            "start_date": str(start_date),
            "end_date": str(end_date),
            "count": len(meals),
            "items": meals,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/by-type/{meal_type}")
def get_meals_by_type(
    meal_type: str,
    current_user: CurrentUser = Depends(get_current_user),
    repo: MealsRepository = Depends(get_meals_repository),
):
    try:
        meals = repo.list_by_meal_type_compatible(
            current_user.id,
            meal_type,
        )

        return {
            "meal_type": meal_type,
            "count": len(meals),
            "items": meals,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


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
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("", status_code=status.HTTP_201_CREATED)
def create_meal(
    meal: MealCreate,
    current_user: CurrentUser = Depends(get_current_user),
    repo: MealsRepository = Depends(get_meals_repository),
):
    """
    Create a meal for the authenticated user.

    `user_id` is never accepted from the client: FastAPI adds it from
    the authenticated Supabase session.
    """
    payload = meal.model_dump(exclude_none=True)
    payload["date"] = str(payload["date"])
    payload["user_id"] = current_user.id

    try:
        response = repo.create_compatible(payload)
        rows = getattr(response, "data", None) or []

        return {
            "created": True,
            "item": rows[0] if rows else payload,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.patch("/{meal_id}")
def update_meal(
    meal_id: str,
    changes: MealUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    repo: MealsRepository = Depends(get_meals_repository),
):
    """
    Update only fields explicitly supplied by the client.
    """
    payload = changes.model_dump(exclude_unset=True)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields supplied",
        )

    try:
        item = repo.update(
            meal_id=meal_id,
            user_id=current_user.id,
            payload=payload,
        )

        return {
            "updated": True,
            "item": item,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{meal_id}",
    status_code=status.HTTP_200_OK,
)
def delete_meal(
    meal_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repo: MealsRepository = Depends(get_meals_repository),
):
    try:
        repo.delete(
            meal_id=meal_id,
            user_id=current_user.id,
        )

        return {
            "deleted": True,
            "id": meal_id,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
