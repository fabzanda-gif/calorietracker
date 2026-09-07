from urllib.parse import parse_qs, urlparse

import pytest

from backend.services.google_calendar_oauth import (
    GOOGLE_CALENDAR_SCOPES,
    GoogleCalendarOAuthError,
    GoogleCalendarOAuthService,
)


def service(**kwargs):
    return GoogleCalendarOAuthService(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri=(
            "https://example.com/"
            "profile/google-calendar/callback"
        ),
        state_secret="state-secret",
        **kwargs,
    )


def test_authorization_url_contains_expected_values():
    url = service().authorization_url(
        "user-1"
    )

    query = parse_qs(
        urlparse(url).query
    )

    assert query["response_type"] == [
        "code"
    ]
    assert query["client_id"] == [
        "client-id"
    ]
    assert query["redirect_uri"] == [
        "https://example.com/"
        "profile/google-calendar/callback"
    ]
    assert query["scope"] == [
        GOOGLE_CALENDAR_SCOPES
    ]
    assert query["access_type"] == [
        "offline"
    ]
    assert query["prompt"] == [
        "consent"
    ]

    service().verify_state(
        query["state"][0],
        "user-1",
    )


def test_state_cannot_be_used_for_another_user():
    oauth = service()

    state = oauth.build_state(
        "user-1"
    )

    with pytest.raises(
        GoogleCalendarOAuthError,
        match="user mismatch",
    ):
        oauth.verify_state(
            state,
            "user-2",
        )


def test_tampered_state_is_rejected():
    oauth = service()

    state = oauth.build_state(
        "user-1"
    )

    with pytest.raises(
        GoogleCalendarOAuthError,
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
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": (
                    GOOGLE_CALENDAR_SCOPES
                ),
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

    assert (
        result["access_token"]
        == "access"
    )
    assert (
        result["refresh_token"]
        == "refresh"
    )
    assert (
        result["scope"]
        == GOOGLE_CALENDAR_SCOPES
    )
    assert (
        result["expires_at"]
        is not None
    )


def test_refresh_preserves_refresh_token():
    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {
                "access_token":
                    "new-access",
                "token_type":
                    "Bearer",
                "expires_in": 3600,
            }

    class Client:
        @staticmethod
        def post(url, **kwargs):
            assert (
                kwargs["data"][
                    "refresh_token"
                ]
                == "refresh"
            )

            return Response()

    result = service(
        http_client=Client()
    ).refresh_access_token(
        "refresh"
    )

    assert (
        result["access_token"]
        == "new-access"
    )
    assert (
        result["refresh_token"]
        == "refresh"
    )
