from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass

import requests

from backend.observability import log_event


_DEFAULT_EXCLUDED_USER_IDS = {
    "3c02c906-a49f-40c5-a349-e45c2f71cfed",
}


@dataclass(frozen=True)
class LoginNotificationResult:
    status: str


def _configured_excluded_user_ids() -> set[str]:
    configured = {
        value.strip()
        for value in os.getenv(
            "LOGIN_ALERT_EXCLUDED_USER_IDS",
            "",
        ).split(",")
        if value.strip()
    }
    return _DEFAULT_EXCLUDED_USER_IDS | configured


def _session_issued_at(access_token: str) -> str:
    try:
        payload_segment = access_token.split(".")[1]
        padding = "=" * (-len(payload_segment) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(
                payload_segment + padding
            )
        )
        return str(payload.get("iat") or "")
    except (IndexError, ValueError, TypeError, json.JSONDecodeError):
        return ""


def _idempotency_key(user_id: str, access_token: str) -> str:
    issued_at = _session_issued_at(access_token)
    material = f"{user_id}:{issued_at or access_token}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"sanosync-login-{digest}"


def send_login_notification(
    *,
    user_id: str,
    access_token: str,
    metadata: dict,
) -> LoginNotificationResult:
    if user_id in _configured_excluded_user_ids():
        return LoginNotificationResult(status="excluded")

    api_key = os.getenv("RESEND_API_KEY", "").strip()
    recipient = os.getenv("LOGIN_ALERT_TO", "").strip()
    sender = os.getenv("LOGIN_ALERT_FROM", "").strip()

    if not api_key or not recipient or not sender:
        log_event(
            "login_notification_skipped",
            reason="not_configured",
        )
        return LoginNotificationResult(status="not_configured")

    email = str(metadata.get("email") or "").strip()
    name = str(
        metadata.get("full_name")
        or metadata.get("name")
        or ""
    ).strip()
    identity = email or user_id

    lines = [
        "Un utente ha effettuato l'accesso a SanoSync.",
        "",
        f"Utente: {name or 'Non disponibile'}",
        f"Email: {identity}",
        f"UID: {user_id}",
    ]

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Idempotency-Key": _idempotency_key(
                    user_id,
                    access_token,
                ),
            },
            json={
                "from": sender,
                "to": [recipient],
                "subject": f"Login SanoSync · {identity}",
                "text": "\n".join(lines),
            },
            timeout=8,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        log_event(
            "login_notification_failed",
            error_type=type(exc).__name__,
        )
        return LoginNotificationResult(status="failed")

    log_event("login_notification_sent")
    return LoginNotificationResult(status="sent")
