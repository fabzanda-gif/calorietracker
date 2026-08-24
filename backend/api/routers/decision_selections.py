from __future__ import annotations

from datetime import date as Date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

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
from backend.services.decision_commit import (
    DecisionCommitError,
    DecisionCommitService,
)
from backend.services.decision_selection import (
    DecisionSelectionError,
    DecisionSelectionService,
)


router = APIRouter(prefix="/days", tags=["decision-selections"])


MEAL_SLOT_TO_TYPE = {
    "breakfast": "Colazione",
    "lunch": "Pranzo",
    "dinner": "Cena",
}


class DecisionSelectionCreate(BaseModel):
    mode: str
    lens: str
    option_index: int = Field(ge=0)
    candidate: dict[str, Any]
    available_kcal: float | None = None
    protein_remaining_g: float | None = None


@router.post(
    "/{day_date}/meals/{meal_slot}/selection",
    status_code=status.HTTP_201_CREATED,
)
def save_decision_selection(
    day_date: Date,
    meal_slot: str,
    data: DecisionSelectionCreate,
    current_user: CurrentUser = Depends(get_current_user),
    repo: DecisionSelectionsRepository = Depends(
        get_decision_selections_repository
    ),
):
    if meal_slot not in MEAL_SLOT_TO_TYPE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown meal slot",
        )

    try:
        event = DecisionSelectionService().build_event(
            user_id=current_user.id,
            day_date=day_date,
            meal_slot=meal_slot,
            meal_type=MEAL_SLOT_TO_TYPE[meal_slot],
            mode=data.mode,
            lens=data.lens,
            candidate=data.candidate,
            option_index=data.option_index,
            available_kcal=data.available_kcal,
            protein_remaining_g=data.protein_remaining_g,
        )

        item = repo.create(event)

        return {
            "saved": True,
            "item": item if item is not None else event,
        }

    except DecisionSelectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post(
    "/{day_date}/meals/{meal_slot}/commit",
    status_code=status.HTTP_201_CREATED,
)
def commit_decision_selection(
    day_date: Date,
    meal_slot: str,
    data: DecisionSelectionCreate,
    current_user: CurrentUser = Depends(get_current_user),
    selections_repo: DecisionSelectionsRepository = Depends(
        get_decision_selections_repository
    ),
    meals_repo: MealsRepository = Depends(
        get_meals_repository
    ),
):
    try:
        return DecisionCommitService(
            selections_repo=selections_repo,
            meals_repo=meals_repo,
        ).commit(
            user_id=current_user.id,
            day_date=day_date,
            meal_slot=meal_slot,
            mode=data.mode,
            lens=data.lens,
            option_index=data.option_index,
            candidate=data.candidate,
            available_kcal=data.available_kcal,
            protein_remaining_g=data.protein_remaining_g,
        )

    except (
        DecisionCommitError,
        DecisionSelectionError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
