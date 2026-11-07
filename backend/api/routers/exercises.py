from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_exercise_library_repository,
)
from backend.repositories.base import RepositoryError
from backend.repositories.exercise_library import (
    ExerciseLibraryRepository,
)


router = APIRouter(
    prefix="/exercises",
    tags=["exercise-library"],
)


@router.get("")
def list_exercises(
    search: str | None = Query(
        default=None,
        max_length=120,
    ),
    body_part: str | None = Query(
        default=None,
        max_length=80,
    ),
    equipment: str | None = Query(
        default=None,
        max_length=80,
    ),
    difficulty: str | None = Query(
        default=None,
        pattern="^(beginner|intermediate|advanced)$",
    ),
    approved_only: bool = False,
    language: str = Query(
        default="it",
        pattern="^[a-z]{2}(-[A-Z]{2})?$",
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: ExerciseLibraryRepository = Depends(
        get_exercise_library_repository
    ),
):
    del current_user

    try:
        items = repo.list_exercises(
            search=search,
            body_part=body_part,
            equipment_key=equipment,
            difficulty=difficulty,
            approved_only=approved_only,
            language=language,
            limit=limit,
            offset=offset,
        )
        return {
            "items": items,
            "count": len(items),
            "limit": limit,
            "offset": offset,
        }
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/{identifier}")
def get_exercise(
    identifier: str,
    language: str = Query(
        default="it",
        pattern="^[a-z]{2}(-[A-Z]{2})?$",
    ),
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: ExerciseLibraryRepository = Depends(
        get_exercise_library_repository
    ),
):
    del current_user

    try:
        item = repo.get_exercise(
            identifier,
            language=language,
        )
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found",
        )

    return item
