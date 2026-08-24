from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_decision_selections_repository,
)
from backend.repositories.base import RepositoryError
from backend.repositories.decision_selections import (
    DecisionSelectionsRepository,
)
from backend.services.decision_learning import (
    DecisionLearningService,
)


router = APIRouter(
    prefix="/insights",
    tags=["decision-learning"],
)


@router.get("/decision-preferences")
def get_decision_preferences(
    limit: int = Query(default=100, ge=1, le=500),
    current_user: CurrentUser = Depends(get_current_user),
    repo: DecisionSelectionsRepository = Depends(
        get_decision_selections_repository
    ),
):
    try:
        events = repo.list_for_user(
            current_user.id,
            limit=limit,
        )

        learned = DecisionLearningService().build(
            events=events,
        )

        return {
            "user_id": current_user.id,
            "event_limit": limit,
            **learned,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
