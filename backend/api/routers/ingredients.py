from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_ingredients_repository,
)
from backend.repositories.base import RepositoryError
from backend.repositories.ingredients import IngredientsRepository
from backend.services.ingredient_names import (
    normalize_ingredient_name,
)


router = APIRouter(
    prefix="/ingredients",
    tags=["ingredients"],
)


class IngredientCreate(BaseModel):
    name: str = Field(min_length=1)

    calories_per_100g: float = Field(default=0, ge=0)
    protein_per_100g: float = Field(default=0, ge=0)
    carbs_per_100g: float = Field(default=0, ge=0)
    fat_per_100g: float = Field(default=0, ge=0)

    default_unit: str = Field(
        default="g",
        min_length=1,
    )


class IngredientUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
    )

    calories_per_100g: float | None = Field(
        default=None,
        ge=0,
    )
    protein_per_100g: float | None = Field(
        default=None,
        ge=0,
    )
    carbs_per_100g: float | None = Field(
        default=None,
        ge=0,
    )
    fat_per_100g: float | None = Field(
        default=None,
        ge=0,
    )

    default_unit: str | None = Field(
        default=None,
        min_length=1,
    )


@router.get("")
def list_ingredients(
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: IngredientsRepository = Depends(
        get_ingredients_repository
    ),
):
    try:
        items = repo.list_for_user(
            current_user.id
        )

        return {
            "count": len(items),
            "items": items,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/{ingredient_id}")
def get_ingredient(
    ingredient_id: str,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: IngredientsRepository = Depends(
        get_ingredients_repository
    ),
):
    try:
        item = repo.get_by_id(
            ingredient_id,
            current_user.id,
        )

        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ingredient not found",
            )

        return {
            "item": item,
        }

    except HTTPException:
        raise
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_ingredient(
    ingredient: IngredientCreate,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: IngredientsRepository = Depends(
        get_ingredients_repository
    ),
):
    payload = ingredient.model_dump()

    payload["name"] = payload["name"].strip()
    payload["normalized_name"] = (
        normalize_ingredient_name(
            payload["name"]
        )
    )
    payload["user_id"] = current_user.id

    try:
        item = repo.create(payload)

        return {
            "created": True,
            "item": (
                item
                if item is not None
                else payload
            ),
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.patch("/{ingredient_id}")
def update_ingredient(
    ingredient_id: str,
    changes: IngredientUpdate,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: IngredientsRepository = Depends(
        get_ingredients_repository
    ),
):
    payload = changes.model_dump(
        exclude_unset=True
    )

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields supplied",
        )

    if "name" in payload:
        payload["name"] = payload[
            "name"
        ].strip()

        payload["normalized_name"] = (
            normalize_ingredient_name(
                payload["name"]
            )
        )

    try:
        existing = repo.get_by_id(
            ingredient_id,
            current_user.id,
        )

        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ingredient not found",
            )

        item = repo.update(
            ingredient_id,
            current_user.id,
            payload,
        )

        return {
            "updated": True,
            "item": item,
        }

    except HTTPException:
        raise
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.delete("/{ingredient_id}")
def delete_ingredient(
    ingredient_id: str,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: IngredientsRepository = Depends(
        get_ingredients_repository
    ),
):
    try:
        existing = repo.get_by_id(
            ingredient_id,
            current_user.id,
        )

        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ingredient not found",
            )

        repo.delete(
            ingredient_id,
            current_user.id,
        )

        return {
            "deleted": True,
            "id": ingredient_id,
        }

    except HTTPException:
        raise
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
