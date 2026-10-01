from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    CurrentUser,
    get_authenticated_supabase,
    get_current_user,
)
from backend.services.special_periods import special_period_defaults


router = APIRouter(prefix="/special-periods", tags=["special-periods"])


class SpecialPeriodCreate(BaseModel):
    period_type: str = Field(pattern="^(vacation|illness)$")
    start_date: date
    end_date: date
    notes: str | None = Field(default=None, max_length=1000)


class SpecialPeriodUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)


def _validate_dates(start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La data di fine non può precedere la data di inizio.",
        )


@router.get("")
def list_special_periods(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    supabase=Depends(get_authenticated_supabase),
):
    query = (
        supabase.table("special_periods")
        .select(
            "id,period_type,start_date,end_date,training_policy,activity_bias,"
            "nutrition_mode,meal_context,notes,created_at,updated_at"
        )
        .eq("user_id", current_user.id)
    )

    if start_date is not None:
        query = query.gte("end_date", str(start_date))
    if end_date is not None:
        query = query.lte("start_date", str(end_date))

    result = query.order("start_date").execute()
    items = result.data or []
    return {"count": len(items), "items": items}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_special_period(
    payload: SpecialPeriodCreate,
    current_user: CurrentUser = Depends(get_current_user),
    supabase=Depends(get_authenticated_supabase),
):
    _validate_dates(payload.start_date, payload.end_date)
    defaults = special_period_defaults(payload.period_type)

    result = (
        supabase.table("special_periods")
        .insert(
            {
                "user_id": current_user.id,
                "period_type": payload.period_type,
                "start_date": str(payload.start_date),
                "end_date": str(payload.end_date),
                "notes": payload.notes.strip() if payload.notes else None,
                **defaults,
            }
        )
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Impossibile salvare il periodo speciale.",
        )
    return result.data[0]


@router.patch("/{period_id}")
def update_special_period(
    period_id: str,
    payload: SpecialPeriodUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    supabase=Depends(get_authenticated_supabase),
):
    current = (
        supabase.table("special_periods")
        .select("id,start_date,end_date")
        .eq("id", period_id)
        .eq("user_id", current_user.id)
        .limit(1)
        .execute()
    )
    rows = current.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Periodo speciale non trovato.")

    start = payload.start_date or date.fromisoformat(str(rows[0]["start_date"]))
    end = payload.end_date or date.fromisoformat(str(rows[0]["end_date"]))
    _validate_dates(start, end)

    changes: dict = {
        "start_date": str(start),
        "end_date": str(end),
        "updated_at": datetime.utcnow().isoformat(),
    }
    if payload.notes is not None:
        changes["notes"] = payload.notes.strip() or None

    result = (
        supabase.table("special_periods")
        .update(changes)
        .eq("id", period_id)
        .eq("user_id", current_user.id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Periodo speciale non trovato.")
    return result.data[0]


@router.delete("/{period_id}")
def delete_special_period(
    period_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    supabase=Depends(get_authenticated_supabase),
):
    (
        supabase.table("special_periods")
        .delete()
        .eq("id", period_id)
        .eq("user_id", current_user.id)
        .execute()
    )
    return {"deleted": True, "id": period_id}
