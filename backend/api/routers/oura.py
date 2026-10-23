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
    get_oura_connections_repository,
)
from backend.repositories.base import RepositoryError
from backend.repositories.oura_connections import (
    OuraConnectionsRepository,
)
from backend.services.oura_oauth import (
    OuraConfigurationError,
    OuraOAuthError,
    OuraOAuthService,
)


router = APIRouter(
    prefix="/integrations/oura",
    tags=["oura"],
)


class OuraExchangeRequest(BaseModel):
    code: str
    state: str


@router.get("/status")
def get_oura_status(
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: OuraConnectionsRepository = Depends(
        get_oura_connections_repository
    ),
):
    try:
        connection = repo.get_status(
            current_user.id
        )
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {
        "connected": connection is not None,
        "connection": connection,
    }


@router.get("/authorize")
def get_oura_authorization(
    current_user: CurrentUser = Depends(
        get_current_user
    ),
):
    try:
        authorization_url = (
            OuraOAuthService().authorization_url(
                current_user.id
            )
        )
    except OuraConfigurationError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=str(exc),
        ) from exc

    return {
        "authorization_url": authorization_url,
    }


@router.post("/exchange")
def exchange_oura_code(
    body: OuraExchangeRequest,
    current_user: CurrentUser = Depends(
        get_current_user
    ),
    repo: OuraConnectionsRepository = Depends(
        get_oura_connections_repository
    ),
):
    try:
        service = OuraOAuthService()
        service.verify_state(
            body.state,
            current_user.id,
        )
        tokens = service.exchange_code(
            body.code
        )

        repo.upsert_tokens(
            user_id=current_user.id,
            values=tokens,
        )
    except OuraConfigurationError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=str(exc),
        ) from exc
    except OuraOAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except RepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {
        "connected": True,
    }
