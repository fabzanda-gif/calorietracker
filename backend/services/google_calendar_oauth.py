from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import secrets
from typing import Any
from urllib.parse import urlencode

import requests


GOOGLE_AUTHORIZE_URL = (
    "https://accounts.google.com/o/oauth2/v2/auth"
)

GOOGLE_TOKEN_URL = (
    "https://oauth2.googleapis.com/token"
)

GOOGLE_CALENDAR_SCOPES = (
    "https://www.googleapis.com/auth/calendar.events"
)


class GoogleCalendarOAuthError(RuntimeError):
    pass


class GoogleCalendarConfigurationError(
    GoogleCalendarOAuthError
):
    pass


class GoogleCalendarOAuthService:
    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
        state_secret: str | None = None,
        http_client: Any | None = None,
    ) -> None:
        self.client_id = (
            client_id
            or os.getenv(
                "GOOGLE_CALENDAR_CLIENT_ID"
            )
            or ""
        ).strip()

        self.client_secret = (
            client_secret
            or os.getenv(
                "GOOGLE_CALENDAR_CLIENT_SECRET"
            )
            or ""
        ).strip()

        self.redirect_uri = (
            redirect_uri
            or os.getenv(
                "GOOGLE_CALENDAR_REDIRECT_URI"
            )
            or ""
        ).strip()

        self.state_secret = (
            state_secret
            or os.getenv(
                "GOOGLE_CALENDAR_OAUTH_STATE_SECRET"
            )
            or ""
        ).strip()

        self.http_client = (
            http_client or requests
        )

        missing = [
            name
            for name, value in (
                (
                    "GOOGLE_CALENDAR_CLIENT_ID",
                    self.client_id,
                ),
                (
                    "GOOGLE_CALENDAR_CLIENT_SECRET",
                    self.client_secret,
                ),
                (
                    "GOOGLE_CALENDAR_REDIRECT_URI",
                    self.redirect_uri,
                ),
                (
                    "GOOGLE_CALENDAR_OAUTH_STATE_SECRET",
                    self.state_secret,
                ),
            )
            if not value
        ]

        if missing:
            raise GoogleCalendarConfigurationError(
                "Missing Google Calendar "
                "configuration: "
                + ", ".join(missing)
            )

    def authorization_url(
        self,
        user_id: str,
    ) -> str:
        state = self.build_state(user_id)

        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": GOOGLE_CALENDAR_SCOPES,
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "true",
                "state": state,
            }
        )

        return (
            f"{GOOGLE_AUTHORIZE_URL}?"
            f"{query}"
        )

    def build_state(
        self,
        user_id: str,
    ) -> str:
        payload = {
            "uid": str(user_id),
            "ts": int(
                datetime.now(
                    timezone.utc
                ).timestamp()
            ),
            "nonce": secrets.token_urlsafe(18),
        }

        raw = json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

        body = (
            base64.urlsafe_b64encode(raw)
            .decode("ascii")
            .rstrip("=")
        )

        signature = hmac.new(
            self.state_secret.encode("utf-8"),
            body.encode("ascii"),
            hashlib.sha256,
        ).digest()

        encoded_signature = (
            base64.urlsafe_b64encode(
                signature
            )
            .decode("ascii")
            .rstrip("=")
        )

        return (
            f"{body}.{encoded_signature}"
        )

    def get_state_user_id(
        self,
        state: str,
        *,
        max_age_seconds: int = 900,
    ) -> str:
        try:
            body, supplied_signature = (
                str(state).split(".", 1)
            )

            expected = hmac.new(
                self.state_secret.encode("utf-8"),
                body.encode("ascii"),
                hashlib.sha256,
            ).digest()

            expected_signature = (
                base64.urlsafe_b64encode(expected)
                .decode("ascii")
                .rstrip("=")
            )

            if not hmac.compare_digest(
                supplied_signature,
                expected_signature,
            ):
                raise GoogleCalendarOAuthError(
                    "Invalid Google OAuth state"
                )

            padded = body + "=" * (-len(body) % 4)

            payload = json.loads(
                base64.urlsafe_b64decode(
                    padded
                ).decode("utf-8")
            )

            user_id = str(
                payload.get("uid") or ""
            ).strip()

            if not user_id:
                raise GoogleCalendarOAuthError(
                    "Invalid Google OAuth state"
                )

            issued_at = int(
                payload.get("ts") or 0
            )

            age = (
                int(
                    datetime.now(
                        timezone.utc
                    ).timestamp()
                )
                - issued_at
            )

            if (
                age < 0
                or age > max_age_seconds
            ):
                raise GoogleCalendarOAuthError(
                    "Expired Google OAuth state"
                )

            return user_id

        except GoogleCalendarOAuthError:
            raise

        except Exception as exc:
            raise GoogleCalendarOAuthError(
                "Invalid Google OAuth state"
            ) from exc


    def verify_state(
        self,
        state: str,
        user_id: str,
        *,
        max_age_seconds: int = 900,
    ) -> None:
        try:
            body, supplied_signature = (
                str(state).split(".", 1)
            )

            expected = hmac.new(
                self.state_secret.encode(
                    "utf-8"
                ),
                body.encode("ascii"),
                hashlib.sha256,
            ).digest()

            expected_signature = (
                base64.urlsafe_b64encode(
                    expected
                )
                .decode("ascii")
                .rstrip("=")
            )

            if not hmac.compare_digest(
                supplied_signature,
                expected_signature,
            ):
                raise GoogleCalendarOAuthError(
                    "Invalid Google OAuth state"
                )

            padded = (
                body
                + "=" * (-len(body) % 4)
            )

            payload = json.loads(
                base64.urlsafe_b64decode(
                    padded
                ).decode("utf-8")
            )

            if (
                str(payload.get("uid"))
                != str(user_id)
            ):
                raise GoogleCalendarOAuthError(
                    "Google OAuth user mismatch"
                )

            issued_at = int(
                payload.get("ts") or 0
            )

            age = (
                int(
                    datetime.now(
                        timezone.utc
                    ).timestamp()
                )
                - issued_at
            )

            if (
                age < 0
                or age > max_age_seconds
            ):
                raise GoogleCalendarOAuthError(
                    "Expired Google OAuth state"
                )

        except GoogleCalendarOAuthError:
            raise

        except Exception as exc:
            raise GoogleCalendarOAuthError(
                "Invalid Google OAuth state"
            ) from exc

    def exchange_code(
        self,
        code: str,
    ) -> dict[str, Any]:
        code = str(code or "").strip()

        if not code:
            raise GoogleCalendarOAuthError(
                "Missing Google authorization code"
            )

        try:
            response = self.http_client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "grant_type": (
                        "authorization_code"
                    ),
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": (
                        self.client_secret
                    ),
                    "redirect_uri": (
                        self.redirect_uri
                    ),
                },
                timeout=20,
            )
        except Exception as exc:
            raise GoogleCalendarOAuthError(
                "Unable to contact Google"
            ) from exc

        if response.status_code >= 400:
            raise GoogleCalendarOAuthError(
                "Google rejected the "
                "authorization code"
            )

        try:
            payload = response.json()
        except Exception as exc:
            raise GoogleCalendarOAuthError(
                "Invalid response from Google"
            ) from exc

        access_token = str(
            payload.get("access_token")
            or ""
        ).strip()

        if not access_token:
            raise GoogleCalendarOAuthError(
                "Google token response "
                "is incomplete"
            )

        refresh_token = (
            str(
                payload.get(
                    "refresh_token"
                )
                or ""
            ).strip()
            or None
        )

        expires_in = int(
            payload.get("expires_in")
            or 0
        )

        expires_at = None

        if expires_in > 0:
            expires_at = (
                datetime.now(timezone.utc)
                + timedelta(
                    seconds=expires_in
                )
            ).isoformat()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": str(
                payload.get("token_type")
                or "Bearer"
            ),
            "scope": str(
                payload.get("scope")
                or GOOGLE_CALENDAR_SCOPES
            ),
            "expires_at": expires_at,
            "updated_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

    def refresh_access_token(
        self,
        refresh_token: str,
    ) -> dict[str, Any]:
        refresh_token = str(
            refresh_token or ""
        ).strip()

        if not refresh_token:
            raise GoogleCalendarOAuthError(
                "Missing Google refresh token"
            )

        try:
            response = self.http_client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "grant_type": (
                        "refresh_token"
                    ),
                    "refresh_token": (
                        refresh_token
                    ),
                    "client_id": self.client_id,
                    "client_secret": (
                        self.client_secret
                    ),
                },
                timeout=20,
            )
        except Exception as exc:
            raise GoogleCalendarOAuthError(
                "Unable to refresh "
                "Google access token"
            ) from exc

        if response.status_code >= 400:
            raise GoogleCalendarOAuthError(
                "Google rejected the "
                "refresh token"
            )

        try:
            payload = response.json()
        except Exception as exc:
            raise GoogleCalendarOAuthError(
                "Invalid refresh response "
                "from Google"
            ) from exc

        access_token = str(
            payload.get("access_token")
            or ""
        ).strip()

        if not access_token:
            raise GoogleCalendarOAuthError(
                "Google refresh response "
                "is incomplete"
            )

        expires_in = int(
            payload.get("expires_in")
            or 0
        )

        expires_at = None

        if expires_in > 0:
            expires_at = (
                datetime.now(timezone.utc)
                + timedelta(
                    seconds=expires_in
                )
            ).isoformat()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": str(
                payload.get("token_type")
                or "Bearer"
            ),
            "scope": str(
                payload.get("scope")
                or GOOGLE_CALENDAR_SCOPES
            ),
            "expires_at": expires_at,
            "updated_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }
