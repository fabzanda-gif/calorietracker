from __future__ import annotations

from datetime import date as Date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_meal_prep_repository,
    get_meals_repository,
    get_recipes_repository,
)
from backend.repositories.base import RepositoryError
from backend.repositories.meal_prep import MealPrepRepository
from backend.repositories.meals import MealsRepository
from backend.repositories.recipes import RecipesRepository
from backend.services.meal_prep import (
    MealPrepError,
    MealPrepNotFoundError,
    MealPrepService,
    MealPrepUnavailableError,
)
from backend.services.meal_prep_logging import (
    MealPrepBatchNotFoundError,
    MealPrepBatchUnavailableError,
    MealPrepLoggingService,
)


router = APIRouter(
    prefix="/meal-prep",
    tags=["meal-prep"],
)


class MealPrepCreate(BaseModel):
    recipe_id: str
    prepared_at: Date
    portions_prepared: int = Field(gt=0)
    expires_at: Date | None = None


class MealPrepConsume(BaseModel):
    portions: int = Field(default=1, gt=0)


class MealPrepRemainingUpdate(BaseModel):
    portions_remaining: int = Field(ge=0)


class MealPrepDiscard(BaseModel):
    portions: int = Field(default=1, gt=0)


class MealPrepStatusUpdate(BaseModel):
    status: str


class MealPrepLogRequest(BaseModel):
    date: Date
    meal_type: str


def _service(
    meal_prep_repo: MealPrepRepository,
    recipes_repo: RecipesRepository,
) -> MealPrepService:
    return MealPrepService(
        meal_prep_repo=meal_prep_repo,
        recipes_repo=recipes_repo,
    )


@router.get("")
def get_meal_prep_inventory(
    available_only: bool = False,
    current_user: CurrentUser = Depends(get_current_user),
    repo: MealPrepRepository = Depends(get_meal_prep_repository),
    recipes_repo: RecipesRepository = Depends(get_recipes_repository),
):
    try:
        items = (
            repo.list_available(current_user.id)
            if available_only
            else repo.list_all(current_user.id)
        )

        enriched_items = []

        for item in items:
            enriched = dict(item)

            recipe_id = item.get("recipe_id")
            image_url = None

            if recipe_id:
                recipe = recipes_repo.get_personal_by_id(
                    recipe_id,
                    current_user.id,
                )

                if recipe is not None:
                    image_url = recipe.get("image_url")

            enriched["image_url"] = image_url
            enriched_items.append(enriched)

        return {
            "count": len(enriched_items),
            "items": enriched_items,
        }
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("", status_code=status.HTTP_201_CREATED)
def create_meal_prep_batch(
    data: MealPrepCreate,
    current_user: CurrentUser = Depends(get_current_user),
    meal_prep_repo: MealPrepRepository = Depends(
        get_meal_prep_repository
    ),
    recipes_repo: RecipesRepository = Depends(
        get_recipes_repository
    ),
):
    try:
        item = _service(
            meal_prep_repo,
            recipes_repo,
        ).create_from_recipe(
            user_id=current_user.id,
            recipe_id=data.recipe_id,
            prepared_at=data.prepared_at,
            portions_prepared=data.portions_prepared,
            expires_at=data.expires_at,
        )
        return {"created": True, "item": item}
    except MealPrepNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except MealPrepError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("/{batch_id}/consume")
def consume_meal_prep(
    batch_id: str,
    data: MealPrepConsume,
    current_user: CurrentUser = Depends(get_current_user),
    meal_prep_repo: MealPrepRepository = Depends(
        get_meal_prep_repository
    ),
    recipes_repo: RecipesRepository = Depends(
        get_recipes_repository
    ),
):
    try:
        item = _service(
            meal_prep_repo,
            recipes_repo,
        ).consume_portion(
            user_id=current_user.id,
            batch_id=batch_id,
            portions=data.portions,
        )
        return {"updated": True, "item": item}
    except MealPrepNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except MealPrepUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except MealPrepError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("/{batch_id}/log")
def log_meal_prep_portion(
    batch_id: str,
    data: MealPrepLogRequest,
    current_user: CurrentUser = Depends(get_current_user),
    meal_prep_repo: MealPrepRepository = Depends(
        get_meal_prep_repository
    ),
    meals_repo: MealsRepository = Depends(get_meals_repository),
):
    try:
        return MealPrepLoggingService(
            meal_prep_repo=meal_prep_repo,
            meals_repo=meals_repo,
        ).log_portion(
            user_id=current_user.id,
            batch_id=batch_id,
            meal_date=data.date,
            meal_type=data.meal_type,
        )
    except MealPrepBatchNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except MealPrepBatchUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.patch("/{batch_id}/remaining")
def update_meal_prep_remaining(
    batch_id: str,
    data: MealPrepRemainingUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    meal_prep_repo: MealPrepRepository = Depends(
        get_meal_prep_repository
    ),
    recipes_repo: RecipesRepository = Depends(
        get_recipes_repository
    ),
):
    try:
        item = _service(
            meal_prep_repo,
            recipes_repo,
        ).set_remaining_portions(
            user_id=current_user.id,
            batch_id=batch_id,
            portions_remaining=data.portions_remaining,
        )
        return {"updated": True, "item": item}
    except MealPrepNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except MealPrepError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("/{batch_id}/discard")
def discard_meal_prep_portions(
    batch_id: str,
    data: MealPrepDiscard,
    current_user: CurrentUser = Depends(get_current_user),
    meal_prep_repo: MealPrepRepository = Depends(
        get_meal_prep_repository
    ),
):
    try:
        batch = meal_prep_repo.get_by_id(
            batch_id,
            current_user.id,
        )

        if batch is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meal prep batch not found",
            )

        remaining = int(
            batch.get("portions_remaining") or 0
        )

        if data.portions > remaining:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot discard more portions than remain in inventory",
            )

        new_remaining = remaining - data.portions

        item = meal_prep_repo.update(
            batch_id,
            current_user.id,
            {
                "portions_remaining": new_remaining,
                "status": (
                    "finished"
                    if new_remaining == 0
                    else "available"
                ),
            },
        )

        if item is None:
            item = {
                **batch,
                "portions_remaining": new_remaining,
                "status": (
                    "finished"
                    if new_remaining == 0
                    else "available"
                ),
            }

        return {
            "updated": True,
            "discarded": data.portions,
            "item": item,
        }

    except HTTPException:
        raise

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.patch("/{batch_id}/status")
def update_meal_prep_status(
    batch_id: str,
    data: MealPrepStatusUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    meal_prep_repo: MealPrepRepository = Depends(
        get_meal_prep_repository
    ),
    recipes_repo: RecipesRepository = Depends(
        get_recipes_repository
    ),
):
    try:
        item = _service(
            meal_prep_repo,
            recipes_repo,
        ).set_status(
            user_id=current_user.id,
            batch_id=batch_id,
            status=data.status,
        )
        return {"updated": True, "item": item}
    except MealPrepNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except MealPrepError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
