from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.dependencies import (
    CurrentUser, get_current_user, get_authenticated_supabase,
)
from backend.repositories.athlete_state import AthleteStateRepository
from backend.repositories.base import RepositoryError
from backend.services.athlete_state import AthleteStateService

router = APIRouter(prefix="/athlete-state", tags=["athlete-state"])


def get_athlete_state_repo(
    supabase=Depends(get_authenticated_supabase),
) -> AthleteStateRepository:
    return AthleteStateRepository(supabase)


@router.get("")
def get_athlete_state(
    as_of: date | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    repo: AthleteStateRepository = Depends(get_athlete_state_repo),
):
    day = as_of or date.today()
    if day > date.today():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Athlete State cannot be calculated for a future date.",
        )
    try:
        history = repo.completed_strength_history(
            current_user.id, as_of=day, days=56,
        )
        profile = repo.training_profile(current_user.id)
        return AthleteStateService().build(
            history=history, as_of=day, profile=profile,
        )
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
