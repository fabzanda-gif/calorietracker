from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from backend.api.dependencies import (
    CurrentUser,
    get_admin_supabase_client,
    get_current_user,
)


router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    onboarding_completed: bool | None = None
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
    response = {
        "id": (
            current_user.authenticated_id
            or current_user.id
        ),
        "metadata": dict(current_user.metadata),
    }

    if current_user.read_only:
        response.update({
            "read_only": True,
            "demo_mode": True,
        })

    return response


_EXPORT_TABLES = (
    "activities",
    "daily_logs",
    "day_briefings",
    "decision_selections",
    "ingredients",
    "meal_prep_batches",
    "meals",
    "pantry_items",
    "planned_activities",
    "recipe_library",
    "recipes",
    "strength_plans",
    "strength_progression_history",
    "strength_workout_exercises",
    "strength_workouts",
    "training_plan_adaptations",
    "training_plans",
    "weekly_schedule",
)


def _response_rows(response: Any) -> list[dict[str, Any]]:
    return list(getattr(response, "data", None) or [])


@router.get("/export")
def export_profile_data(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Export the user's SanoSync data as portable JSON.

    OAuth access/refresh tokens are deliberately excluded. Integration
    sections contain only non-secret connection metadata.
    """
    if current_user.read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Data export is unavailable for the demo account",
        )

    supabase = get_admin_supabase_client()
    user_id = current_user.id
    exported: dict[str, Any] = {}

    try:
        for table_name in _EXPORT_TABLES:
            response = (
                supabase
                .table(table_name)
                .select("*")
                .eq("user_id", user_id)
                .execute()
            )
            exported[table_name] = _response_rows(response)

        meal_ids = [
            row["id"]
            for row in exported["meals"]
            if row.get("id") is not None
        ]
        recipe_ids = [
            row["id"]
            for row in exported["recipe_library"]
            if row.get("id") is not None
        ]

        exported["meal_ingredients"] = []
        if meal_ids:
            response = (
                supabase
                .table("meal_ingredients")
                .select("*")
                .in_("meal_id", meal_ids)
                .execute()
            )
            exported["meal_ingredients"] = _response_rows(response)

        exported["recipe_ingredients"] = []
        if recipe_ids:
            response = (
                supabase
                .table("recipe_ingredients")
                .select("*")
                .in_("recipe_id", recipe_ids)
                .execute()
            )
            exported["recipe_ingredients"] = _response_rows(response)

        google_connection = (
            supabase
            .table("google_calendar_connections")
            .select(
                "calendar_id,scope,connected_at,"
                "updated_at,last_synced_at"
            )
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        oura_connection = (
            supabase
            .table("oura_connections")
            .select(
                "oura_user_id,scope,expires_at,"
                "connected_at,updated_at"
            )
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        exported["integrations"] = {
            "google_calendar": (
                _response_rows(google_connection)[0]
                if _response_rows(google_connection)
                else None
            ),
            "oura": (
                _response_rows(oura_connection)[0]
                if _response_rows(oura_connection)
                else None
            ),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to export SanoSync data",
        ) from exc

    return {
        "schema_version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "profile": {
            "id": (
                current_user.authenticated_id
                or current_user.id
            ),
            "metadata": dict(current_user.metadata),
        },
        "data": exported,
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


@router.delete("/account")
def delete_account(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, bool]:
    url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not service_role_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase admin configuration is missing",
        )

    authenticated_user_id = (
        current_user.authenticated_id
        or current_user.id
    )

    try:
        response = requests.delete(
            (
                f"{url.rstrip('/')}/auth/v1/admin/users/"
                f"{authenticated_user_id}"
            ),
            headers={
                "apikey": service_role_key,
                "Authorization": f"Bearer {service_role_key}",
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to delete Supabase account",
        ) from exc

    if not response.ok:
        raise HTTPException(
            status_code=response.status_code,
            detail="Unable to delete Supabase account",
        )

    return {"deleted": True}
