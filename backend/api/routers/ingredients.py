from __future__ import annotations

import base64
import binascii
from typing import Any, Literal

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
from backend.services.nutrition_label_vision import (
    NutritionLabelVisionError,
    NutritionLabelVisionService,
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

    grams_per_unit: float | None = Field(
        default=None,
        gt=0,
    )

    default_quantity: float | None = Field(
        default=None,
        gt=0,
    )

    kind: Literal[
        "ingredient",
        "product",
        "prepared_food",
    ] = "ingredient"

    meal_slots: list[
        Literal[
            "breakfast",
            "lunch",
            "snack",
            "dinner",
        ]
    ] = Field(default_factory=list)


class NutritionLabelScanRequest(BaseModel):
    content_base64: str = Field(
        min_length=1,
    )
    mime_type: str = Field(
        min_length=1,
        max_length=80,
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

    grams_per_unit: float | None = Field(
        default=None,
        gt=0,
    )

    default_quantity: float | None = Field(
        default=None,
        gt=0,
    )

    kind: Literal[
        "ingredient",
        "product",
        "prepared_food",
    ] | None = None

    meal_slots: list[
        Literal[
            "breakfast",
            "lunch",
            "snack",
            "dinner",
        ]
    ] | None = None


@router.post("/scan-label")
def scan_nutrition_label(
    request: NutritionLabelScanRequest,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
):
    _ = current_user

    if request.mime_type not in {
        "image/jpeg",
        "image/png",
        "image/webp",
    }:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                "Formato immagine non supportato."
            ),
        )

    try:
        image_bytes = base64.b64decode(
            request.content_base64,
            validate=True,
        )
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Immagine non valida.",
        ) from exc

    if len(image_bytes) > 8 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                "L'immagine supera il limite "
                "di 8 MB."
            ),
        )

    try:
        result = (
            NutritionLabelVisionService()
            .analyze(
                image_bytes=image_bytes,
                mime_type=request.mime_type,
            )
        )
    except NutritionLabelVisionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Non riesco a leggere "
                "l'etichetta nutrizionale."
            ),
        ) from exc

    return {
        "result": result,
    }


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
