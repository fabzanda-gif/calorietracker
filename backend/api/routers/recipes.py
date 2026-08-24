from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_ingredients_repository,
    get_recipe_ingredients_repository,
    get_recipes_repository,
)
from backend.repositories.base import RepositoryError
from backend.repositories.ingredients import IngredientsRepository
from backend.repositories.recipe_ingredients import (
    RecipeIngredientsRepository,
)
from backend.repositories.recipes import RecipesRepository
from backend.services.structured_recipe import (
    StructuredRecipeError,
    StructuredRecipeService,
)


router = APIRouter(prefix="/recipes", tags=["recipes"])


class StructuredRecipeIngredient(BaseModel):
    ingredient_id: str
    quantity: float = Field(gt=0)
    unit: str = "g"
    quantity_g: float = Field(gt=0)


class RecipeCreate(BaseModel):
    name: str = Field(min_length=1)
    meal_type: str | None = None
    category: str | None = None
    recipe_servings: float | None = Field(default=None, gt=0)
    calories: float = 0
    protein: float = 0
    carbs: float = 0
    fat: float = 0
    notes: str | None = None
    ingredients_json: Any | None = None
    structured_ingredients: list[StructuredRecipeIngredient] | None = None
    is_shared: bool = False
    image_url: str | None = None


class RecipeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    meal_type: str | None = None
    category: str | None = None
    recipe_servings: float | None = Field(default=None, gt=0)
    calories: float | None = None
    protein: float | None = None
    carbs: float | None = None
    fat: float | None = None
    notes: str | None = None
    ingredients_json: Any | None = None
    structured_ingredients: list[StructuredRecipeIngredient] | None = None
    image_url: str | None = None


class RecipeShareUpdate(BaseModel):
    is_shared: bool


@router.get("")
def get_personal_recipes(
    current_user: CurrentUser = Depends(get_current_user),
    repo: RecipesRepository = Depends(get_recipes_repository),
):
    try:
        items = repo.list_personal(current_user.id)
        return {"count": len(items), "items": items}
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/available")
def get_available_recipes(
    current_user: CurrentUser = Depends(get_current_user),
    repo: RecipesRepository = Depends(get_recipes_repository),
):
    try:
        items = repo.list_available(current_user.id)
        return {"count": len(items), "items": items}
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/shared")
def get_shared_recipes(
    exclude_mine: bool = Query(default=False),
    current_user: CurrentUser = Depends(get_current_user),
    repo: RecipesRepository = Depends(get_recipes_repository),
):
    try:
        items = repo.list_shared(
            exclude_user_id=current_user.id if exclude_mine else None
        )
        return {"count": len(items), "items": items}
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/{recipe_id}")
def get_recipe(
    recipe_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repo: RecipesRepository = Depends(get_recipes_repository),
    recipe_ingredients_repo: RecipeIngredientsRepository = Depends(
        get_recipe_ingredients_repository
    ),
):
    try:
        item = repo.get_personal_by_id(
            recipe_id,
            current_user.id,
        )

        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recipe not found",
            )

        structured = (
            recipe_ingredients_repo.list_for_recipe(
                recipe_id
            )
        )

        return {
            "item": {
                **item,
                "structured_ingredients": structured,
            }
        }
    except HTTPException:
        raise
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("", status_code=status.HTTP_201_CREATED)
def create_recipe(
    recipe: RecipeCreate,
    current_user: CurrentUser = Depends(get_current_user),
    repo: RecipesRepository = Depends(get_recipes_repository),
    ingredients_repo: IngredientsRepository = Depends(
        get_ingredients_repository
    ),
    recipe_ingredients_repo: RecipeIngredientsRepository = Depends(
        get_recipe_ingredients_repository
    ),
):
    payload = recipe.model_dump(exclude_none=True)
    structured = payload.pop(
        "structured_ingredients",
        None,
    )

    try:
        if structured is not None:
            result = StructuredRecipeService(
                recipes_repo=repo,
                ingredients_repo=ingredients_repo,
                recipe_ingredients_repo=recipe_ingredients_repo,
            ).create(
                user_id=current_user.id,
                recipe_payload=payload,
                structured_ingredients=structured,
            )

            return {
                "created": True,
                "structured": True,
                "item": result["recipe"],
                "recipe_ingredients": result[
                    "recipe_ingredients"
                ],
            }

        payload["user_id"] = current_user.id
        item = repo.create(payload)

        return {
            "created": True,
            "structured": False,
            "item": item if item is not None else payload,
        }
    except StructuredRecipeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.patch("/{recipe_id}")
def update_recipe(
    recipe_id: str,
    changes: RecipeUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    repo: RecipesRepository = Depends(get_recipes_repository),
    ingredients_repo: IngredientsRepository = Depends(
        get_ingredients_repository
    ),
    recipe_ingredients_repo: RecipeIngredientsRepository = Depends(
        get_recipe_ingredients_repository
    ),
):
    payload = changes.model_dump(exclude_unset=True)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields supplied",
        )

    structured = payload.pop(
        "structured_ingredients",
        None,
    )

    try:
        if structured is not None:
            result = StructuredRecipeService(
                recipes_repo=repo,
                ingredients_repo=ingredients_repo,
                recipe_ingredients_repo=recipe_ingredients_repo,
            ).update(
                user_id=current_user.id,
                recipe_id=recipe_id,
                recipe_payload=payload,
                structured_ingredients=structured,
            )

            return {
                "updated": True,
                "structured": True,
                "item": result["recipe"],
                "recipe_ingredients": result[
                    "recipe_ingredients"
                ],
            }

        item = repo.update(
            recipe_id,
            current_user.id,
            payload,
        )

        return {
            "updated": True,
            "structured": False,
            "item": item,
        }
    except StructuredRecipeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.patch("/{recipe_id}/sharing")
def update_recipe_sharing(
    recipe_id: str,
    sharing: RecipeShareUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    repo: RecipesRepository = Depends(get_recipes_repository),
):
    try:
        item = repo.set_shared(
            recipe_id,
            current_user.id,
            sharing.is_shared,
        )
        return {
            "updated": True,
            "is_shared": sharing.is_shared,
            "item": item,
        }
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.delete("/{recipe_id}")
def delete_recipe(
    recipe_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repo: RecipesRepository = Depends(get_recipes_repository),
):
    try:
        repo.delete(recipe_id, current_user.id)
        return {"deleted": True, "id": recipe_id}
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
