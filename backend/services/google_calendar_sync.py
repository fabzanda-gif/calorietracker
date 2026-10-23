from __future__ import annotations

from datetime import (
    date,
    datetime,
    time,
    timedelta,
    timezone,
)
import os
from typing import Any

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
from backend.services.google_calendar_api import (
    GoogleCalendarApi,
    GoogleCalendarApiError,
)
from backend.services.google_calendar_oauth import (
    GoogleCalendarOAuthError,
    GoogleCalendarOAuthService,
)


class GoogleCalendarSyncError(RuntimeError):
    pass


class GoogleCalendarSyncService:
    def __init__(
        self,
        *,
        connections_repo:
            GoogleCalendarConnectionsRepository,
        events_repo:
            GoogleCalendarEventsRepository,
        planned_repo:
            PlannedActivitiesRepository,
        strength_repo:
            StrengthWorkoutsRepository,
        calendar_api: GoogleCalendarApi | None = None,
        oauth_service:
            GoogleCalendarOAuthService | None = None,
    ) -> None:
        self.connections_repo = connections_repo
        self.events_repo = events_repo
        self.planned_repo = planned_repo
        self.strength_repo = strength_repo
        self.calendar_api = (
            calendar_api
            or GoogleCalendarApi()
        )
        self.oauth_service = (
            oauth_service
            or GoogleCalendarOAuthService()
        )
        self.timezone = (
            os.getenv(
                "GOOGLE_CALENDAR_TIMEZONE",
                "Europe/Rome",
            ).strip()
            or "Europe/Rome"
        )

    def sync_range(
        self,
        *,
        user_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, int]:
        connection = (
            self.connections_repo.get_private(
                user_id
            )
        )

        if connection is None:
            raise GoogleCalendarSyncError(
                "Google Calendar is not connected"
            )

        access_token = self._access_token(
            user_id=user_id,
            connection=connection,
        )

        calendar_id = str(
            connection.get("calendar_id")
            or "primary"
        )

        created = 0
        updated = 0
        deleted = 0

        planned = self.planned_repo.list_range(
            user_id,
            start_date,
            end_date,
        )

        strength = (
            self.strength_repo.list_date_range(
                user_id,
                start_date,
                end_date,
            )
        )

        for item in planned:
            result = self._sync_source(
                user_id=user_id,
                source_type="planned_activity",
                source=item,
                access_token=access_token,
                calendar_id=calendar_id,
            )
            created += int(
                result == "created"
            )
            updated += int(
                result == "updated"
            )

        for item in strength:
            result = self._sync_source(
                user_id=user_id,
                source_type="strength_workout",
                source=item,
                access_token=access_token,
                calendar_id=calendar_id,
            )
            created += int(
                result == "created"
            )
            updated += int(
                result == "updated"
            )

        for mapping in (
            self.events_repo.list_for_user(
                user_id
            )
        ):
            source_type = str(
                mapping["source_type"]
            )
            source_id = str(
                mapping["source_id"]
            )

            if self._source_exists(
                user_id=user_id,
                source_type=source_type,
                source_id=source_id,
            ):
                continue

            self.calendar_api.delete_event(
                access_token=access_token,
                calendar_id=str(
                    mapping.get(
                        "google_calendar_id"
                    )
                    or calendar_id
                ),
                event_id=str(
                    mapping["google_event_id"]
                ),
            )

            self.events_repo.delete_by_source(
                user_id=user_id,
                source_type=source_type,
                source_id=source_id,
            )
            deleted += 1

        return {
            "created": created,
            "updated": updated,
            "deleted": deleted,
        }

    def _sync_source(
        self,
        *,
        user_id: str,
        source_type: str,
        source: dict[str, Any],
        access_token: str,
        calendar_id: str,
    ) -> str:
        source_id = str(source["id"])

        mapping = (
            self.events_repo.get_by_source(
                user_id=user_id,
                source_type=source_type,
                source_id=source_id,
            )
        )

        event = self._event_payload(
            source_type=source_type,
            source=source,
        )

        if mapping is None:
            remote = (
                self.calendar_api.create_event(
                    access_token=access_token,
                    calendar_id=calendar_id,
                    event=event,
                )
            )

            self.events_repo.upsert_mapping(
                user_id=user_id,
                source_type=source_type,
                source_id=source_id,
                google_event_id=str(
                    remote["id"]
                ),
                google_calendar_id=calendar_id,
            )

            return "created"

        self.calendar_api.update_event(
            access_token=access_token,
            calendar_id=str(
                mapping.get(
                    "google_calendar_id"
                )
                or calendar_id
            ),
            event_id=str(
                mapping["google_event_id"]
            ),
            event=event,
        )

        return "updated"

    def _source_exists(
        self,
        *,
        user_id: str,
        source_type: str,
        source_id: str,
    ) -> bool:
        if source_type == "planned_activity":
            return (
                self.planned_repo.get(
                    source_id,
                    user_id,
                )
                is not None
            )

        if source_type == "strength_workout":
            return (
                self.strength_repo.get(
                    user_id,
                    source_id,
                )
                is not None
            )

        return False

    def _event_payload(
        self,
        *,
        source_type: str,
        source: dict[str, Any],
    ) -> dict[str, Any]:
        if source_type == "planned_activity":
            return self._planned_event(
                source
            )

        return self._strength_event(
            source
        )

    def _planned_event(
        self,
        source: dict[str, Any],
    ) -> dict[str, Any]:
        status = str(
            source.get("status")
            or "planned"
        )

        title = str(
            source.get("title")
            or "Allenamento"
        )

        if status == "skipped":
            title = f"[Saltato] {title}"

        description_parts = [
            "SanoSync · attività pianificata",
            f"Stato: {status}",
        ]

        notes = str(
            source.get("notes")
            or ""
        ).strip()

        if notes:
            description_parts.append(notes)

        event = {
            "summary": title,
            "description":
                "\n".join(description_parts),
            "extendedProperties": {
                "private": {
                    "sanosync_source_type":
                        "planned_activity",
                    "sanosync_source_id":
                        str(source["id"]),
                }
            },
        }

        scheduled_date = date.fromisoformat(
            str(source["scheduled_date"])
        )

        scheduled_time = (
            source.get("scheduled_time")
        )

        if scheduled_time:
            start_time = time.fromisoformat(
                str(scheduled_time)
            )

            start = datetime.combine(
                scheduled_date,
                start_time,
            )

            duration = int(
                source.get(
                    "duration_minutes"
                )
                or 60
            )

            end = (
                start
                + timedelta(
                    minutes=duration
                )
            )

            event["start"] = {
                "dateTime":
                    start.isoformat(),
                "timeZone":
                    self.timezone,
            }
            event["end"] = {
                "dateTime":
                    end.isoformat(),
                "timeZone":
                    self.timezone,
            }

            return event

        event["start"] = {
            "date":
                scheduled_date.isoformat()
        }
        event["end"] = {
            "date":
                (
                    scheduled_date
                    + timedelta(days=1)
                ).isoformat()
        }

        return event

    def _strength_event(
        self,
        source: dict[str, Any],
    ) -> dict[str, Any]:
        scheduled_date = date.fromisoformat(
            str(source["scheduled_date"])
        )

        status = str(
            source.get("status")
            or "planned"
        )

        title = str(
            source.get("title")
            or "Forza"
        )

        if status == "skipped":
            title = f"[Saltato] {title}"

        duration = source.get(
            "estimated_duration_minutes"
        )

        description = [
            "SanoSync · allenamento forza",
            f"Stato: {status}",
        ]

        if duration:
            description.append(
                f"Durata stimata: "
                f"{duration} min"
            )

        return {
            "summary": f"Forza · {title}",
            "description":
                "\n".join(description),
            "start": {
                "date":
                    scheduled_date.isoformat()
            },
            "end": {
                "date":
                    (
                        scheduled_date
                        + timedelta(days=1)
                    ).isoformat()
            },
            "extendedProperties": {
                "private": {
                    "sanosync_source_type":
                        "strength_workout",
                    "sanosync_source_id":
                        str(source["id"]),
                }
            },
        }

    def _access_token(
        self,
        *,
        user_id: str,
        connection: dict[str, Any],
    ) -> str:
        access_token = str(
            connection.get(
                "access_token"
            )
            or ""
        ).strip()

        expires_at_raw = (
            connection.get("expires_at")
        )

        refresh = False

        if not access_token:
            refresh = True

        if expires_at_raw:
            try:
                expires_at = (
                    datetime.fromisoformat(
                        str(
                            expires_at_raw
                        ).replace(
                            "Z",
                            "+00:00",
                        )
                    )
                )

                if (
                    expires_at
                    <= datetime.now(
                        timezone.utc
                    )
                    + timedelta(minutes=2)
                ):
                    refresh = True
            except ValueError:
                refresh = True

        if not refresh:
            return access_token

        refresh_token = str(
            connection.get(
                "refresh_token"
            )
            or ""
        ).strip()

        try:
            tokens = (
                self.oauth_service
                .refresh_access_token(
                    refresh_token
                )
            )
        except GoogleCalendarOAuthError as exc:
            raise GoogleCalendarSyncError(
                str(exc)
            ) from exc

        self.connections_repo.upsert_tokens(
            user_id=user_id,
            values=tokens,
        )

        return str(
            tokens["access_token"]
        )
