from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, status

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
)
from backend.services.login_notifications import (
    send_login_notification,
)


router = APIRouter(
    prefix="/auth-events",
    tags=["auth-events"],
)


@router.post(
    "/login",
    status_code=status.HTTP_202_ACCEPTED,
)
async def record_login(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    authenticated_id = (
        current_user.authenticated_id
        or current_user.id
    )
    result = await asyncio.to_thread(
        send_login_notification,
        user_id=authenticated_id,
        access_token=current_user.access_token,
        metadata=current_user.metadata,
    )
    return {"status": result.status}
