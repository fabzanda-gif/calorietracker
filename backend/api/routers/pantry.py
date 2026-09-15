from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_ingredients_repository,
    get_pantry_repository,
)
from backend.repositories.base import RepositoryError
from backend.repositories.ingredients import IngredientsRepository
from backend.repositories.pantry import PantryRepository


router = APIRouter(
    prefix="/pantry",
    tags=["pantry"],
)


class PantryCreate(BaseModel):
    ingredient_id: str
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1)
    quantity_mode: str = "weight"
    grams_per_portion: float | None = Field(default=None, gt=0)
    expires_at: date | None = None

    @model_validator(mode="after")
    def validate_quantity_mode(self):
        if self.quantity_mode not in {"weight", "portion"}:
            raise ValueError("Invalid quantity mode")

        if (
            self.quantity_mode == "portion"
            and self.grams_per_portion is None
        ):
            raise ValueError(
                "grams_per_portion is required for portions"
            )

        if self.quantity_mode == "weight":
            self.grams_per_portion = None

        return self


class PantryUpdate(BaseModel):
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, min_length=1)
    quantity_mode: str | None = None
    grams_per_portion: float | None = Field(default=None, gt=0)
    expires_at: date | None = None


def _serialize(item: dict | None) -> dict | None:
    if item is None:
        return None

    result = dict(item)
    ingredient = result.pop("ingredients", None)

    if isinstance(ingredient, dict):
        result["ingredient_name"] = ingredient.get("name")
    else:
        result["ingredient_name"] = None

    return result


@router.get("")
def list_pantry(
    current_user: CurrentUser = Depends(get_current_user),
    repo: PantryRepository = Depends(get_pantry_repository),
):
    try:
        items = [
            _serialize(item)
            for item in repo.list_for_user(current_user.id)
        ]

        return {
            "count": len(items),
            "items": items,
        }
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("", status_code=status.HTTP_201_CREATED)
def create_pantry_item(
    data: PantryCreate,
    current_user: CurrentUser = Depends(get_current_user),
    repo: PantryRepository = Depends(get_pantry_repository),
    ingredients_repo: IngredientsRepository = Depends(
        get_ingredients_repository
    ),
):
    try:
        ingredient = ingredients_repo.get_by_id(
            data.ingredient_id,
            current_user.id,
        )

        if ingredient is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ingredient not found",
            )

        payload = data.model_dump(mode="json")
        payload["user_id"] = current_user.id
        payload["unit"] = payload["unit"].strip()

        if payload["quantity_mode"] == "portion":
            payload["unit"] = "portion"
        else:
            payload["grams_per_portion"] = None

        item = repo.create(payload)

        if item is None:
            item = {
                **payload,
                "ingredient_name": ingredient.get("name"),
            }
        else:
            item = _serialize(item)
            if not item.get("ingredient_name"):
                item["ingredient_name"] = ingredient.get("name")

        return {
            "created": True,
            "item": item,
        }

    except HTTPException:
        raise
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.patch("/{item_id}")
def update_pantry_item(
    item_id: str,
    changes: PantryUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    repo: PantryRepository = Depends(get_pantry_repository),
):
    payload = changes.model_dump(
        exclude_unset=True,
        mode="json",
    )

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields supplied",
        )

    if "unit" in payload:
        payload["unit"] = payload["unit"].strip()

    if (
        "quantity_mode" in payload
        and payload["quantity_mode"]
        not in {"weight", "portion"}
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid quantity mode",
        )

    try:
        existing = repo.get_by_id(
            item_id,
            current_user.id,
        )

        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pantry item not found",
            )

        resulting_mode = payload.get(
            "quantity_mode",
            existing.get("quantity_mode", "weight"),
        )

        resulting_grams = (
            payload.get("grams_per_portion")
            if "grams_per_portion" in payload
            else existing.get("grams_per_portion")
        )

        if resulting_mode == "portion":
            if resulting_grams is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        "grams_per_portion is required "
                        "for portions"
                    ),
                )

            payload["unit"] = "portion"
        else:
            payload["grams_per_portion"] = None

        item = repo.update(
            item_id,
            current_user.id,
            payload,
        )

        return {
            "updated": True,
            "item": _serialize(item)
            if item is not None
            else {
                **_serialize(existing),
                **payload,
            },
        }

    except HTTPException:
        raise
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.delete("/{item_id}")
def delete_pantry_item(
    item_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repo: PantryRepository = Depends(get_pantry_repository),
):
    try:
        existing = repo.get_by_id(
            item_id,
            current_user.id,
        )

        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pantry item not found",
            )

        repo.delete(
            item_id,
            current_user.id,
        )

        return {
            "deleted": True,
            "id": item_id,
        }

    except HTTPException:
        raise
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
