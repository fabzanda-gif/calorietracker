from urllib.parse import parse_qs, urlparse

import pytest

from backend.services.oura_oauth import (
    OuraOAuthError,
    OuraOAuthService,
)


def service(**kwargs):
    return OuraOAuthService(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri=(
            "https://example.com/profile/oura/callback"
        ),
        state_secret="state-secret",
        **kwargs,
    )


def test_authorization_url_contains_expected_values():
    url = service().authorization_url("user-1")
    query = parse_qs(urlparse(url).query)

    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == [
        "https://example.com/profile/oura/callback"
    ]
    assert query["scope"] == [
        "daily heartrate workout"
    ]

    service().verify_state(
        query["state"][0],
        "user-1",
    )


def test_state_cannot_be_used_for_another_user():
    oauth = service()
    state = oauth.build_state("user-1")

    with pytest.raises(
        OuraOAuthError,
        match="user mismatch",
    ):
        oauth.verify_state(
            state,
            "user-2",
        )


def test_tampered_state_is_rejected():
    oauth = service()
    state = oauth.build_state("user-1")

    with pytest.raises(
        OuraOAuthError,
        match="Invalid",
    ):
        oauth.verify_state(
            state + "changed",
            "user-1",
        )


def test_code_exchange_normalizes_token_payload():
    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {
                "access_token": "access",
                "refresh_token": "refresh",
                "token_type": "bearer",
                "expires_in": 3600,
                "scope": "daily workout",
            }

    class Client:
        @staticmethod
        def post(url, **kwargs):
            assert (
                kwargs["data"]["code"]
                == "authorization-code"
            )
            return Response()

    result = service(
        http_client=Client()
    ).exchange_code(
        "authorization-code"
    )

    assert result["access_token"] == "access"
    assert result["refresh_token"] == "refresh"
    assert result["scope"] == "daily workout"
    assert result["expires_at"] is not None
