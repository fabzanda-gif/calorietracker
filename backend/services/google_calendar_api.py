from __future__ import annotations

from typing import Any
from urllib.parse import quote

import requests


GOOGLE_CALENDAR_API = (
    "https://www.googleapis.com/calendar/v3"
)


class GoogleCalendarApiError(RuntimeError):
    pass


class GoogleCalendarApi:
    def __init__(
        self,
        *,
        http_client: Any | None = None,
    ) -> None:
        self.http_client = http_client or requests

    def _events_url(
        self,
        calendar_id: str,
    ) -> str:
        encoded = quote(
            calendar_id,
            safe="",
        )
        return (
            f"{GOOGLE_CALENDAR_API}/calendars/"
            f"{encoded}/events"
        )

    def create_event(
        self,
        *,
        access_token: str,
        calendar_id: str,
        event: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            response = self.http_client.post(
                self._events_url(calendar_id),
                headers={
                    "Authorization":
                        f"Bearer {access_token}",
                    "Content-Type":
                        "application/json",
                },
                json=event,
                timeout=20,
            )
        except Exception as exc:
            raise GoogleCalendarApiError(
                "Unable to create Google Calendar event"
            ) from exc

        return self._json_response(
            response,
            "create",
        )

    def update_event(
        self,
        *,
        access_token: str,
        calendar_id: str,
        event_id: str,
        event: dict[str, Any],
    ) -> dict[str, Any]:
        url = (
            f"{self._events_url(calendar_id)}/"
            f"{quote(event_id, safe='')}"
        )

        try:
            response = self.http_client.put(
                url,
                headers={
                    "Authorization":
                        f"Bearer {access_token}",
                    "Content-Type":
                        "application/json",
                },
                json=event,
                timeout=20,
            )
        except Exception as exc:
            raise GoogleCalendarApiError(
                "Unable to update Google Calendar event"
            ) from exc

        return self._json_response(
            response,
            "update",
        )

    def delete_event(
        self,
        *,
        access_token: str,
        calendar_id: str,
        event_id: str,
    ) -> None:
        url = (
            f"{self._events_url(calendar_id)}/"
            f"{quote(event_id, safe='')}"
        )

        try:
            response = self.http_client.delete(
                url,
                headers={
                    "Authorization":
                        f"Bearer {access_token}",
                },
                timeout=20,
            )
        except Exception as exc:
            raise GoogleCalendarApiError(
                "Unable to delete Google Calendar event"
            ) from exc

        if response.status_code in (
            200,
            204,
            404,
            410,
        ):
            return

        raise GoogleCalendarApiError(
            "Google Calendar rejected event deletion"
        )

    @staticmethod
    def _json_response(
        response: Any,
        action: str,
    ) -> dict[str, Any]:
        if response.status_code >= 400:
            raise GoogleCalendarApiError(
                "Google Calendar rejected event "
                f"{action}"
            )

        try:
            payload = response.json()
        except Exception as exc:
            raise GoogleCalendarApiError(
                "Invalid response from Google Calendar"
            ) from exc

        if not payload.get("id"):
            raise GoogleCalendarApiError(
                "Google Calendar event response "
                "has no id"
            )

        return payload
