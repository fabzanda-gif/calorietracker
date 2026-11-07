from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from typing import Literal

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


@router.get("/catalog/status")
def get_catalog_status(
    current_user: CurrentUser = Depends(get_current_user),
    repo: ExerciseLibraryRepository = Depends(
        get_exercise_library_repository
    ),
):
    del current_user
    try:
        return repo.catalog_status()
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


class ExercisePreferenceUpdate(BaseModel):
    preference: Literal["preferred", "excluded"]


@router.get("/preferences")
def get_exercise_preferences(
    current_user: CurrentUser = Depends(get_current_user),
    repo: ExerciseLibraryRepository = Depends(
        get_exercise_library_repository
    ),
):
    try:
        items = repo.list_user_preferences(current_user.id)
        return {"items": items, "count": len(items)}
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.put("/{identifier}/preference")
def update_exercise_preference(
    identifier: str,
    payload: ExercisePreferenceUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    repo: ExerciseLibraryRepository = Depends(
        get_exercise_library_repository
    ),
):
    if current_user.read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only account",
        )
    try:
        exercise = repo.get_exercise(identifier)
        if exercise is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Exercise not found",
            )
        return repo.save_user_preference(
            current_user.id,
            exercise["id"],
            payload.preference,
        )
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.delete("/{identifier}/preference", status_code=204)
def delete_exercise_preference(
    identifier: str,
    current_user: CurrentUser = Depends(get_current_user),
    repo: ExerciseLibraryRepository = Depends(
        get_exercise_library_repository
    ),
):
    if current_user.read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only account",
        )
    try:
        exercise = repo.get_exercise(identifier)
        if exercise is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Exercise not found",
            )
        repo.remove_user_preference(current_user.id, exercise["id"])
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/{identifier}/alternatives")
def get_exercise_alternatives(
    identifier: str,
    equipment: str | None = Query(
        default=None,
        max_length=80,
    ),
    language: str = Query(
        default="it",
        pattern="^[a-z]{2}(-[A-Z]{2})?$",
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=50,
    ),
    current_user: CurrentUser = Depends(get_current_user),
    repo: ExerciseLibraryRepository = Depends(
        get_exercise_library_repository
    ),
):
    try:
        items = repo.list_alternatives(
            identifier,
            language=language,
            equipment_key=equipment,
            limit=limit,
            user_id=current_user.id,
        )
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    if items is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found",
        )
    return {"items": items, "count": len(items)}


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
