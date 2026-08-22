from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.dependencies import CurrentUser, get_current_user
from backend.repositories.activities import ActivitiesRepository
from backend.repositories.base import RepositoryError


router = APIRouter(
    prefix="/activities",
    tags=["activities"],
)


class ActivityCreate(BaseModel):
    date: date
    activity_name: str = Field(min_length=1)
    burned_calories: int = Field(ge=0)


class ActivityUpdate(BaseModel):
    activity_name: str | None = None
    burned_calories: int | None = Field(default=None, ge=0)


def get_activities_repository(
    current_user: CurrentUser = Depends(get_current_user),
) -> ActivitiesRepository:
    """
    Build an authenticated Supabase client for activity queries.

    We reuse the authenticated token already resolved by get_current_user.
    """
    from backend.api.dependencies import _supabase_settings
    from supabase import create_client

    url, key = _supabase_settings()
    client = create_client(url, key)
    client.postgrest.auth(current_user.access_token)

    return ActivitiesRepository(client)


@router.get("/{activity_date}")
def get_activities_for_date(
    activity_date: date,
    current_user: CurrentUser = Depends(get_current_user),
    repo: ActivitiesRepository = Depends(get_activities_repository),
):
    try:
        rows = repo.list_for_date(
            user_id=current_user.id,
            log_date=activity_date,
        )

        return {
            "date": str(activity_date),
            "count": len(rows),
            "items": rows,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("", status_code=status.HTTP_201_CREATED)
def create_activity(
    activity: ActivityCreate,
    current_user: CurrentUser = Depends(get_current_user),
    repo: ActivitiesRepository = Depends(get_activities_repository),
):
    payload = activity.model_dump()
    payload["date"] = str(payload["date"])
    payload["user_id"] = current_user.id

    try:
        item = repo.create(payload)

        return {
            "created": True,
            "item": item if item is not None else payload,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.patch("/{activity_id}")
def update_activity(
    activity_id: str,
    changes: ActivityUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    repo: ActivitiesRepository = Depends(get_activities_repository),
):
    payload = changes.model_dump(exclude_unset=True)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields supplied",
        )

    try:
        item = repo.update(
            activity_id=activity_id,
            user_id=current_user.id,
            payload=payload,
        )

        return {
            "updated": True,
            "item": item,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.delete("/{activity_id}")
def delete_activity(
    activity_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repo: ActivitiesRepository = Depends(get_activities_repository),
):
    try:
        repo.delete(
            activity_id=activity_id,
            user_id=current_user.id,
        )

        return {
            "deleted": True,
            "id": activity_id,
        }

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
