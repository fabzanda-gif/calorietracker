from __future__ import annotations

from typing import Any

from .base import BaseRepository, RepositoryError


class GoogleCalendarEventsRepository(BaseRepository):
    table_name = "google_calendar_events"

    def list_for_user(
        self,
        user_id: str,
    ) -> list[dict[str, Any]]:
        try:
            response = (
                self.table
                .select("*")
                .eq("user_id", user_id)
                .execute()
            )
            return self._data(response)
        except Exception as exc:
            raise RepositoryError(
                "Unable to load Google Calendar mappings"
            ) from exc

    def get_by_source(
        self,
        *,
        user_id: str,
        source_type: str,
        source_id: str,
    ) -> dict[str, Any] | None:
        try:
            response = (
                self.table
                .select("*")
                .eq("user_id", user_id)
                .eq("source_type", source_type)
                .eq("source_id", source_id)
                .limit(1)
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                "Unable to load Google Calendar mapping"
            ) from exc

    def upsert_mapping(
        self,
        *,
        user_id: str,
        source_type: str,
        source_id: str,
        google_event_id: str,
        google_calendar_id: str,
    ) -> dict[str, Any] | None:
        payload = {
            "user_id": user_id,
            "source_type": source_type,
            "source_id": source_id,
            "google_event_id": google_event_id,
            "google_calendar_id": google_calendar_id,
        }

        try:
            response = (
                self.table
                .upsert(
                    payload,
                    on_conflict=(
                        "user_id,source_type,source_id"
                    ),
                )
                .execute()
            )
            rows = self._data(response)
            return rows[0] if rows else None
        except Exception as exc:
            raise RepositoryError(
                "Unable to save Google Calendar mapping"
            ) from exc

    def delete_by_source(
        self,
        *,
        user_id: str,
        source_type: str,
        source_id: str,
    ) -> None:
        try:
            (
                self.table
                .delete()
                .eq("user_id", user_id)
                .eq("source_type", source_type)
                .eq("source_id", source_id)
                .execute()
            )
        except Exception as exc:
            raise RepositoryError(
                "Unable to delete Google Calendar mapping"
            ) from exc
