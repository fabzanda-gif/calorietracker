from backend.services.login_notifications import (
    send_login_notification,
)


OWNER_ID = "3c02c906-a49f-40c5-a349-e45c2f71cfed"


def test_owner_login_is_excluded(monkeypatch):
    def unexpected_post(*args, **kwargs):
        raise AssertionError("Resend must not be called")

    monkeypatch.setattr(
        "backend.services.login_notifications.requests.post",
        unexpected_post,
    )

    result = send_login_notification(
        user_id=OWNER_ID,
        access_token="token",
        metadata={"email": "fab.zanda@gmail.com"},
    )

    assert result.status == "excluded"


def test_missing_configuration_does_not_fail_login(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("LOGIN_ALERT_TO", raising=False)
    monkeypatch.delenv("LOGIN_ALERT_FROM", raising=False)

    result = send_login_notification(
        user_id="another-user",
        access_token="token",
        metadata={},
    )

    assert result.status == "not_configured"


def test_resend_uses_session_idempotency(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "secret")
    monkeypatch.setenv("LOGIN_ALERT_TO", "owner@example.com")
    monkeypatch.setenv(
        "LOGIN_ALERT_FROM",
        "SanoSync <login@example.com>",
    )
    calls = []

    class Response:
        def raise_for_status(self):
            return None

    def fake_post(*args, **kwargs):
        calls.append((args, kwargs))
        return Response()

    monkeypatch.setattr(
        "backend.services.login_notifications.requests.post",
        fake_post,
    )

    first = send_login_notification(
        user_id="another-user",
        access_token="header.eyJpYXQiOjEyM30.signature",
        metadata={"email": "user@example.com"},
    )
    second = send_login_notification(
        user_id="another-user",
        access_token="header.eyJpYXQiOjEyM30.signature",
        metadata={"email": "user@example.com"},
    )

    assert first.status == "sent"
    assert second.status == "sent"
    assert len(calls) == 2
    first_key = calls[0][1]["headers"]["Idempotency-Key"]
    second_key = calls[1][1]["headers"]["Idempotency-Key"]
    assert first_key == second_key
