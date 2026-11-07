from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    CurrentUser,
    get_activities_repository,
    get_current_user,
    get_meals_repository,
    get_strength_workout_logs_repository,
    get_weight_repository,
)
from backend.api.routers.profile import ProfileUpdate, update_profile
from backend.repositories.activities import ActivitiesRepository
from backend.repositories.base import RepositoryError
from backend.repositories.meals import MealsRepository
from backend.repositories.strength_logs import StrengthWorkoutLogsRepository
from backend.repositories.weight import WeightRepository
from backend.services.adaptive_macros import AdaptiveMacroService

router = APIRouter(prefix="/adaptive-macros", tags=["adaptive-macros"])


class MacroApplyRequest(BaseModel):
    preview_id: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    confirm: Literal[True]
    logging_complete_confirmed: Literal[True]


def _fresh_preview(
    *,
    as_of: date,
    user: CurrentUser,
    meals_repo: MealsRepository,
    activities_repo: ActivitiesRepository,
    strength_logs_repo: StrengthWorkoutLogsRepository,
    weight_repo: WeightRepository,
) -> dict:
    if as_of > date.today():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Cannot analyze future dates.",
        )
    start = as_of - timedelta(days=27)
    try:
        owner = user.id
        weights = weight_repo.history_range(owner, start, as_of)
        meals = meals_repo.list_date_range(
            owner, start, as_of,
            columns="id,date,calories,protein,carbs,fat",
        )
        activities = activities_repo.list_date_range(owner, start, as_of)
        strength = strength_logs_repo.list_date_range(owner, start, as_of)
        return AdaptiveMacroService().build(
            as_of=as_of,
            metadata=user.metadata,
            weights=weights,
            meals=meals,
            activities=activities,
            strength_logs=strength,
        )
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/preview")
def preview_adaptive_macros(
    as_of: date | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    meals_repo: MealsRepository = Depends(get_meals_repository),
    activities_repo: ActivitiesRepository = Depends(get_activities_repository),
    strength_logs_repo: StrengthWorkoutLogsRepository = Depends(
        get_strength_workout_logs_repository
    ),
    weight_repo: WeightRepository = Depends(get_weight_repository),
):
    return _fresh_preview(
        as_of=as_of or date.today(),
        user=current_user,
        meals_repo=meals_repo,
        activities_repo=activities_repo,
        strength_logs_repo=strength_logs_repo,
        weight_repo=weight_repo,
    )


@router.post("/apply")
def apply_adaptive_macro_proposal(
    request: MacroApplyRequest,
    current_user: CurrentUser = Depends(get_current_user),
    meals_repo: MealsRepository = Depends(get_meals_repository),
    activities_repo: ActivitiesRepository = Depends(get_activities_repository),
    strength_logs_repo: StrengthWorkoutLogsRepository = Depends(
        get_strength_workout_logs_repository
    ),
    weight_repo: WeightRepository = Depends(get_weight_repository),
):
    if current_user.read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only accounts cannot change nutrition goals.",
        )
    # Re-read all source data and goal metadata. A client preview is
    # evidence of what the user reviewed, not a trusted command payload.
    fresh = _fresh_preview(
        as_of=date.today(),
        user=current_user,
        meals_repo=meals_repo,
        activities_repo=activities_repo,
        strength_logs_repo=strength_logs_repo,
        weight_repo=weight_repo,
    )
    proposal = fresh.get("proposal")
    if not proposal or fresh["preview_id"] != request.preview_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Proposal is missing or stale. Refresh the preview before accepting.",
        )
    if proposal["goal_mode"] not in {"loss", "gain"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This goal cannot be adjusted.",
        )

    # Supabase Auth updates user metadata using the same existing profile
    # path. Only the server-derived adjustment is sent, never a client value.
    updated = update_profile(
        ProfileUpdate(
            goal_mode=proposal["goal_mode"],
            goal_adjustment_kcal=proposal["proposed_goal_adjustment_kcal"],
        ),
        current_user=current_user,
    )
    return {
        "applied": True,
        "updated_goal_mode": proposal["goal_mode"],
        "updated_goal_adjustment_kcal": proposal["proposed_goal_adjustment_kcal"],
        "profile": updated,
    }
