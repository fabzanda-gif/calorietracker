from __future__ import annotations

from datetime import date as Date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.dependencies import CurrentUser, get_current_user
from backend.repositories.base import RepositoryError
from backend.repositories.weight import WeightRepository


router = APIRouter(
    prefix="/weight",
    tags=["weight"],
)


class WeightCreate(BaseModel):
    date: Date
    weight: float = Field(gt=0)


class WeightUpdate(BaseModel):
    date: Date | None = None
    weight: float | None = Field(default=None, gt=0)


def get_weight_repository(
    current_user: CurrentUser = Depends(get_current_user),
) -> WeightRepository:
    """
    Create an authenticated Supabase client for weight queries.
    """
    from backend.api.dependencies import _supabase_settings
    from supabase import create_client

    url, key = _supabase_settings()
    client = create_client(url, key)
    client.postgrest.auth(current_user.access_token)

    return WeightRepository(client)


@router.get("")
def get_weight_history(
    current_user: CurrentUser = Depends(get_current_user),
    repo: WeightRepository = Depends(get_weight_repository),
):
    try:
        rows = repo.history(current_user.id)

        return {
            "count": len(rows),
            "items": rows,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/latest")
def get_latest_weight(
    current_user: CurrentUser = Depends(get_current_user),
    repo: WeightRepository = Depends(get_weight_repository),
):
    try:
        row = repo.latest(current_user.id)

        return {
            "item": row,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("", status_code=status.HTTP_201_CREATED)
def create_weight(
    payload: WeightCreate,
    current_user: CurrentUser = Depends(get_current_user),
    repo: WeightRepository = Depends(get_weight_repository),
):
    try:
        item = repo.save(
            user_id=current_user.id,
            log_date=payload.date,
            weight=payload.weight,
        )

        return {
            "created": True,
            "item": item,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.patch("/{row_id}")
def update_weight(
    row_id: str,
    payload: WeightUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    repo: WeightRepository = Depends(get_weight_repository),
):
    if payload.weight is None and payload.date is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields supplied",
        )

    try:
        if payload.date is not None:
            if payload.weight is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Weight is required when changing date",
                )

            item = repo.move_weight(
                row_id=row_id,
                user_id=current_user.id,
                new_date=payload.date,
                weight=payload.weight,
            )

        else:
            item = repo.update_weight(
                row_id=row_id,
                user_id=current_user.id,
                weight=payload.weight,
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


@router.delete("/{row_id}")
def delete_weight(
    row_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repo: WeightRepository = Depends(get_weight_repository),
):
    try:
        item = repo.delete_weight(
            row_id=row_id,
            user_id=current_user.id,
        )

        return {
            "deleted": True,
            "id": row_id,
            "item": item,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
