from __future__ import annotations

from datetime import date as Date, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_weekly_schedule_repository,
)
from backend.repositories.base import RepositoryError
from backend.repositories.weekly_schedule import (
    WeeklyScheduleRepository,
)


router = APIRouter(
    prefix="/weekly-schedule",
    tags=["weekly-schedule"],
)


Context = Literal["home", "office", "free"]


DAY_NAMES = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


class WeeklyScheduleDay(BaseModel):
    day_of_week: int = Field(ge=1, le=7)
    context: Context


class WeeklyScheduleUpdate(BaseModel):
    week_start: Date
    days: list[WeeklyScheduleDay]


def _monday(value: Date) -> Date:
    return value - timedelta(days=value.weekday())


def _default_schedule(
    metadata: dict[str, Any],
) -> dict[str, Context]:
    stored = metadata.get("weekly_schedule")

    if not isinstance(stored, dict):
        stored = {}

    result: dict[str, Context] = {}

    for day in DAY_NAMES:
        value = stored.get(day)

        if value not in ("home", "office", "free"):
            value = "home"

        result[day] = value

    return result


def _resolve_schedule(
    current_user: CurrentUser,
    rows: list[dict[str, Any]],
    week_start: Date,
) -> dict[str, Any]:
    days = _default_schedule(current_user.metadata)
    overrides: dict[str, Context] = {}

    for row in rows:
        day_number = row.get("day_of_week")
        context = row.get("context")

        if (
            isinstance(day_number, int)
            and 1 <= day_number <= 7
            and context in ("home", "office", "free")
        ):
            day_name = DAY_NAMES[day_number - 1]
            days[day_name] = context
            overrides[day_name] = context

    return {
        "week_start": week_start.isoformat(),
        "days": days,
        "overrides": overrides,
    }


@router.get("")
def get_weekly_schedule(
    week_start: Date,
    current_user: CurrentUser = Depends(get_current_user),
    repo: WeeklyScheduleRepository = Depends(
        get_weekly_schedule_repository,
    ),
) -> dict[str, Any]:
    week_start = _monday(week_start)

    try:
        rows = repo.list_for_week(
            current_user.id,
            week_start,
        )

        return _resolve_schedule(
            current_user=current_user,
            rows=rows,
            week_start=week_start,
        )

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.put("")
def update_weekly_schedule(
    payload: WeeklyScheduleUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    repo: WeeklyScheduleRepository = Depends(
        get_weekly_schedule_repository,
    ),
) -> dict[str, Any]:
    week_start = _monday(payload.week_start)

    try:
        for item in payload.days:
            repo.upsert_day(
                user_id=current_user.id,
                week_start=week_start,
                day_of_week=item.day_of_week,
                context=item.context,
            )

        rows = repo.list_for_week(
            current_user.id,
            week_start,
        )

        return _resolve_schedule(
            current_user=current_user,
            rows=rows,
            week_start=week_start,
        )

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
