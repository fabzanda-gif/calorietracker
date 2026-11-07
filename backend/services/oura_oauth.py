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


OURA_AUTHORIZE_URL = (
    "https://cloud.ouraring.com/oauth/authorize"
)
OURA_TOKEN_URL = (
    "https://api.ouraring.com/oauth/token"
)
OURA_SCOPES = "daily heartrate workout"


class OuraOAuthError(RuntimeError):
    pass


class OuraConfigurationError(OuraOAuthError):
    pass


class OuraOAuthService:
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
            or os.getenv("OURA_CLIENT_ID")
            or ""
        ).strip()
        self.client_secret = (
            client_secret
            or os.getenv("OURA_CLIENT_SECRET")
            or ""
        ).strip()
        self.redirect_uri = (
            redirect_uri
            or os.getenv("OURA_REDIRECT_URI")
            or ""
        ).strip()
        self.state_secret = (
            state_secret
            or os.getenv("OURA_OAUTH_STATE_SECRET")
            or ""
        ).strip()
        self.http_client = http_client or requests

        missing = [
            name
            for name, value in (
                ("OURA_CLIENT_ID", self.client_id),
                (
                    "OURA_CLIENT_SECRET",
                    self.client_secret,
                ),
                (
                    "OURA_REDIRECT_URI",
                    self.redirect_uri,
                ),
                (
                    "OURA_OAUTH_STATE_SECRET",
                    self.state_secret,
                ),
            )
            if not value
        ]

        if missing:
            raise OuraConfigurationError(
                "Missing Oura configuration: "
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
                "scope": OURA_SCOPES,
                "state": state,
            }
        )

        return f"{OURA_AUTHORIZE_URL}?{query}"

    def build_state(
        self,
        user_id: str,
    ) -> str:
        payload = {
            "uid": str(user_id),
            "ts": int(
                datetime.now(timezone.utc).timestamp()
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
            base64.urlsafe_b64encode(signature)
            .decode("ascii")
            .rstrip("=")
        )

        return f"{body}.{encoded_signature}"

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
                raise OuraOAuthError(
                    "Invalid Oura OAuth state"
                )

            padded = body + "=" * (-len(body) % 4)
            payload = json.loads(
                base64.urlsafe_b64decode(
                    padded
                ).decode("utf-8")
            )

            if str(payload.get("uid")) != str(user_id):
                raise OuraOAuthError(
                    "Oura OAuth user mismatch"
                )

            issued_at = int(payload.get("ts") or 0)
            age = (
                int(
                    datetime.now(
                        timezone.utc
                    ).timestamp()
                )
                - issued_at
            )

            if age < 0 or age > max_age_seconds:
                raise OuraOAuthError(
                    "Expired Oura OAuth state"
                )
        except OuraOAuthError:
            raise
        except Exception as exc:
            raise OuraOAuthError(
                "Invalid Oura OAuth state"
            ) from exc

    def exchange_code(
        self,
        code: str,
    ) -> dict[str, Any]:
        code = str(code or "").strip()

        if not code:
            raise OuraOAuthError(
                "Missing Oura authorization code"
            )

        try:
            response = self.http_client.post(
                OURA_TOKEN_URL,
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
            raise OuraOAuthError(
                "Unable to contact Oura"
            ) from exc

        if response.status_code >= 400:
            raise OuraOAuthError(
                "Oura rejected the authorization code"
            )

        try:
            payload = response.json()
        except Exception as exc:
            raise OuraOAuthError(
                "Invalid response from Oura"
            ) from exc

        access_token = str(
            payload.get("access_token") or ""
        ).strip()
        refresh_token = str(
            payload.get("refresh_token") or ""
        ).strip()

        if not access_token or not refresh_token:
            raise OuraOAuthError(
                "Oura token response is incomplete"
            )

        expires_in = int(
            payload.get("expires_in") or 0
        )

        expires_at = None

        if expires_in > 0:
            expires_at = (
                datetime.now(timezone.utc)
                + timedelta(seconds=expires_in)
            ).isoformat()

        scope = payload.get("scope")

        if isinstance(scope, list):
            scope = " ".join(
                str(item)
                for item in scope
            )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": str(
                payload.get("token_type")
                or "bearer"
            ),
            "scope": (
                str(scope)
                if scope is not None
                else None
            ),
            "expires_at": expires_at,
            "updated_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }
