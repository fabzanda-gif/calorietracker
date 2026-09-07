from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel

from backend.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_google_calendar_connections_repository,
)
from backend.repositories.base import (
    RepositoryError,
)
from backend.repositories.google_calendar_connections import (
    GoogleCalendarConnectionsRepository,
)
from backend.services.google_calendar_oauth import (
    GoogleCalendarConfigurationError,
    GoogleCalendarOAuthError,
    GoogleCalendarOAuthService,
)


router = APIRouter(
    prefix="/integrations/google-calendar",
    tags=["google-calendar"],
)


class GoogleCalendarExchangeRequest(
    BaseModel
):
    code: str
    state: str


@router.get("/status")
def get_google_calendar_status(
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: GoogleCalendarConnectionsRepository = Depends(
        get_google_calendar_connections_repository
    ),
):
    try:
        connection = repo.get_status(
            current_user.id
        )

    except RepositoryError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=str(exc),
        ) from exc

    return {
        "connected": connection is not None,
        "connection": connection,
    }


@router.get("/authorize")
def get_google_calendar_authorization(
    current_user: CurrentUser = Depends(
        get_current_user
    ),
):
    try:
        authorization_url = (
            GoogleCalendarOAuthService()
            .authorization_url(
                current_user.id
            )
        )

    except GoogleCalendarConfigurationError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=str(exc),
        ) from exc

    return {
        "authorization_url":
            authorization_url,
    }


@router.post("/exchange")
def exchange_google_calendar_code(
    body: GoogleCalendarExchangeRequest,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: GoogleCalendarConnectionsRepository = Depends(
        get_google_calendar_connections_repository
    ),
):
    try:
        service = (
            GoogleCalendarOAuthService()
        )

        service.verify_state(
            body.state,
            current_user.id,
        )

        tokens = service.exchange_code(
            body.code
        )

        if not tokens.get(
            "refresh_token"
        ):
            existing = repo.get_private(
                current_user.id
            )

            existing_refresh = (
                existing or {}
            ).get("refresh_token")

            if existing_refresh:
                tokens[
                    "refresh_token"
                ] = existing_refresh
            else:
                raise GoogleCalendarOAuthError(
                    "Google did not provide "
                    "a refresh token. "
                    "Reconnect Calendar "
                    "and grant access again."
                )

        repo.upsert_tokens(
            user_id=current_user.id,
            values=tokens,
        )

    except GoogleCalendarConfigurationError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=str(exc),
        ) from exc

    except GoogleCalendarOAuthError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=str(exc),
        ) from exc

    except RepositoryError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=str(exc),
        ) from exc

    return {
        "connected": True,
    }


@router.delete("/connection")
def disconnect_google_calendar(
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: GoogleCalendarConnectionsRepository = Depends(
        get_google_calendar_connections_repository
    ),
):
    try:
        repo.delete(
            current_user.id
        )

    except RepositoryError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=str(exc),
        ) from exc

    return {
        "connected": False,
    }
