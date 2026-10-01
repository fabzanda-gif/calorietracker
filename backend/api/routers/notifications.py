from __future__ import annotations

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from pywebpush import WebPushException, webpush

from backend.api.dependencies import (
    CurrentUser,
    get_admin_supabase_client,
    get_current_user,
)


router = APIRouter(prefix="/notifications", tags=["notifications"])


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=1)
    auth: str = Field(min_length=1)


class PushSubscriptionPayload(BaseModel):
    endpoint: str = Field(min_length=1)
    keys: PushKeys
    timezone: str = Field(default="UTC", min_length=1, max_length=128)
    reminder_hour: int = Field(default=8, ge=6, le=11)


class PushUnsubscribePayload(BaseModel):
    endpoint: str = Field(min_length=1)


def _public_key() -> str:
    value = os.getenv("WEB_PUSH_VAPID_PUBLIC_KEY", "").strip()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Push notifications are not configured",
        )
    return value


def _private_key() -> str:
    value = os.getenv("WEB_PUSH_VAPID_PRIVATE_KEY", "").strip()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Push notifications are not configured",
        )
    return value.replace("\\n", "\n")


def _subject() -> str:
    return os.getenv(
        "WEB_PUSH_VAPID_SUBJECT",
        "mailto:support@sanosync.app",
    ).strip()


def _safe_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
        return value
    except ZoneInfoNotFoundError:
        return "UTC"


@router.get("/vapid-public-key")
def get_vapid_public_key():
    return {"public_key": _public_key()}


@router.get("/training/settings")
def get_training_notification_settings(
    endpoint: str = Query(min_length=1),
    current_user: CurrentUser = Depends(get_current_user),
):
    result = (
        get_admin_supabase_client()
        .table("push_subscriptions")
        .select("enabled,timezone,reminder_hour")
        .eq("user_id", current_user.id)
        .eq("endpoint", endpoint)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    if not rows:
        return {
            "enabled": False,
            "timezone": "UTC",
            "reminder_hour": 8,
        }

    row = rows[0]
    return {
        "enabled": bool(row.get("enabled")),
        "timezone": str(row.get("timezone") or "UTC"),
        "reminder_hour": int(row.get("reminder_hour") or 8),
    }


@router.post("/training/subscribe")
def subscribe_to_training_notifications(
    payload: PushSubscriptionPayload,
    current_user: CurrentUser = Depends(get_current_user),
):
    client = get_admin_supabase_client()
    timezone = _safe_timezone(payload.timezone)

    result = (
        client.table("push_subscriptions")
        .upsert(
            {
                "user_id": current_user.id,
                "endpoint": payload.endpoint,
                "p256dh": payload.keys.p256dh,
                "auth": payload.keys.auth,
                "enabled": True,
                "timezone": timezone,
                "reminder_hour": payload.reminder_hour,
                "updated_at": datetime.utcnow().isoformat(),
            },
            on_conflict="endpoint",
        )
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to save push subscription",
        )

    return {
        "enabled": True,
        "timezone": timezone,
        "reminder_hour": payload.reminder_hour,
    }


@router.post("/training/unsubscribe")
def unsubscribe_from_training_notifications(
    payload: PushUnsubscribePayload,
    current_user: CurrentUser = Depends(get_current_user),
):
    (
        get_admin_supabase_client()
        .table("push_subscriptions")
        .update(
            {
                "enabled": False,
                "updated_at": datetime.utcnow().isoformat(),
            }
        )
        .eq("user_id", current_user.id)
        .eq("endpoint", payload.endpoint)
        .execute()
    )

    return {"enabled": False}


def _format_training_body(activity: dict) -> str:
    title = str(activity.get("title") or "Allenamento pianificato").strip()
    details: list[str] = []

    duration = activity.get("duration_minutes")
    if duration:
        details.append(f"{int(duration)} min")

    distance = activity.get("distance_meters")
    if distance:
        km = float(distance) / 1000
        details.append(f"{km:g} km")

    scheduled_time = activity.get("scheduled_time")
    if scheduled_time:
        details.append(str(scheduled_time)[:5])

    suffix = f" · {' · '.join(details)}" if details else ""
    return f"{title}{suffix}. Apri SanoSync per vedere il piano di oggi."


@router.post("/training/dispatch")
def dispatch_training_notifications(
    x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret"),
):
    expected_secret = os.getenv(
        "TRAINING_NOTIFICATION_CRON_SECRET",
        "",
    ).strip()

    if not expected_secret or x_cron_secret != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid cron secret",
        )

    private_key = _private_key()
    subject = _subject()
    client = get_admin_supabase_client()

    subscriptions_result = (
        client.table("push_subscriptions")
        .select(
            "id,user_id,endpoint,p256dh,auth,timezone,"
            "reminder_hour,last_notified_date"
        )
        .eq("enabled", True)
        .execute()
    )

    subscriptions = subscriptions_result.data or []
    sent = 0
    skipped = 0
    disabled = 0

    for subscription in subscriptions:
        timezone_name = _safe_timezone(
            str(subscription.get("timezone") or "UTC")
        )
        now_local = datetime.now(ZoneInfo(timezone_name))
        reminder_hour = int(subscription.get("reminder_hour") or 8)

        if not (reminder_hour <= now_local.hour < 12):
            skipped += 1
            continue

        local_date = now_local.date().isoformat()
        if str(subscription.get("last_notified_date") or "") == local_date:
            skipped += 1
            continue

        activities_result = (
            client.table("planned_activities")
            .select(
                "id,title,activity_type,duration_minutes,"
                "distance_meters,scheduled_time,status"
            )
            .eq("user_id", subscription["user_id"])
            .eq("scheduled_date", local_date)
            .eq("status", "planned")
            .order("scheduled_time")
            .limit(1)
            .execute()
        )

        activities = activities_result.data or []
        if not activities:
            skipped += 1
            continue

        push_payload = {
            "title": "Allenamento oggi 💪",
            "body": _format_training_body(activities[0]),
            "url": "/activities",
            "date": local_date,
        }

        try:
            webpush(
                subscription_info={
                    "endpoint": subscription["endpoint"],
                    "keys": {
                        "p256dh": subscription["p256dh"],
                        "auth": subscription["auth"],
                    },
                },
                data=json.dumps(push_payload),
                vapid_private_key=private_key,
                vapid_claims={"sub": subject},
                ttl=43200,
            )
        except WebPushException as exc:
            response = getattr(exc, "response", None)
            if response is not None and response.status_code in {404, 410}:
                (
                    client.table("push_subscriptions")
                    .update(
                        {
                            "enabled": False,
                            "updated_at": datetime.utcnow().isoformat(),
                        }
                    )
                    .eq("id", subscription["id"])
                    .execute()
                )
                disabled += 1
            continue

        (
            client.table("push_subscriptions")
            .update(
                {
                    "last_notified_date": local_date,
                    "updated_at": datetime.utcnow().isoformat(),
                }
            )
            .eq("id", subscription["id"])
            .execute()
        )
        sent += 1

    return {
        "sent": sent,
        "skipped": skipped,
        "disabled": disabled,
        "checked": len(subscriptions),
    }
