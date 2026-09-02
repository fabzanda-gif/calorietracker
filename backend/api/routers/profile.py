from __future__ import annotations

import os
from typing import Any

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from backend.api.dependencies import CurrentUser, get_current_user


router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    gender: str | None = None
    birth_date: str | None = None
    height: float | None = Field(default=None, gt=0)
    target_weight: float | None = Field(default=None, gt=0)
    deficit_plan: str | None = None
    deficit_target_kcal: float | None = Field(default=None, ge=0)
    goal_mode: str | None = None
    goal_adjustment_kcal: float | None = Field(default=None, ge=0)
    protein_goal_enabled: bool | None = None
    protein_goal_g: float | None = Field(default=None, gt=0)
    language: str | None = None
    city: str | None = None
    office_lunch: bool | None = None
    weekly_schedule: dict[str, str] | None = None


@router.get("")
def get_profile(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "id": current_user.id,
        "metadata": dict(current_user.metadata),
    }


@router.put("")
def update_profile(
    payload: ProfileUpdate,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase configuration is missing",
        )

    updates = payload.model_dump(exclude_unset=True)

    try:
        response = requests.put(
            f"{url.rstrip('/')}/auth/v1/user",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {current_user.access_token}",
                "Content-Type": "application/json",
            },
            json={"data": updates},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to update Supabase profile",
        ) from exc

    if not response.ok:
        raise HTTPException(
            status_code=response.status_code,
            detail="Unable to update Supabase profile",
        )

    data = response.json()

    # Supabase Auth può restituire l'utente direttamente oppure
    # annidato sotto "user". Gestiamo entrambe le forme.
    user = data.get("user") or data

    return {
        "id": user.get("id", current_user.id),
        "metadata": user.get("user_metadata") or {},
    }
