from __future__ import annotations

from datetime import date

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
    get_google_calendar_events_repository,
    get_planned_activities_repository,
    get_strength_workouts_repository,
)
from backend.repositories.base import (
    RepositoryError,
)
from backend.repositories.google_calendar_connections import (
    GoogleCalendarConnectionsRepository,
)
from backend.repositories.google_calendar_events import (
    GoogleCalendarEventsRepository,
)
from backend.repositories.planned_activities import (
    PlannedActivitiesRepository,
)
from backend.repositories.strength_workouts import (
    StrengthWorkoutsRepository,
)
from backend.services.google_calendar_sync import (
    GoogleCalendarSyncError,
    GoogleCalendarSyncService,
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
    repo: GoogleCalendarConnectionsRepository = Depends(
        get_google_calendar_connections_repository
    ),
):
    try:
        service = (
            GoogleCalendarOAuthService()
        )

        user_id = service.get_state_user_id(
            body.state
        )

        tokens = service.exchange_code(
            body.code
        )

        if not tokens.get(
            "refresh_token"
        ):
            existing = repo.get_private(
                user_id
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
            user_id=user_id,
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


@router.post("/sync")
def sync_google_calendar(
    start_date: date,
    end_date: date,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    connections_repo:
        GoogleCalendarConnectionsRepository = Depends(
            get_google_calendar_connections_repository
        ),
    events_repo:
        GoogleCalendarEventsRepository = Depends(
            get_google_calendar_events_repository
        ),
    planned_repo:
        PlannedActivitiesRepository = Depends(
            get_planned_activities_repository
        ),
    strength_repo:
        StrengthWorkoutsRepository = Depends(
            get_strength_workouts_repository
        ),
):
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Google Calendar sync range",
        )

    if (end_date - start_date).days > 366:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Calendar sync range is too large",
        )

    try:
        result = GoogleCalendarSyncService(
            connections_repo=connections_repo,
            events_repo=events_repo,
            planned_repo=planned_repo,
            strength_repo=strength_repo,
        ).sync_range(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

        return {
            "synced": True,
            **result,
        }

    except GoogleCalendarSyncError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


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
