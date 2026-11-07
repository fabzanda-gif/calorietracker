from datetime import date

from backend.services.google_calendar_sync import (
    GoogleCalendarSyncService,
)


class ConnectionsRepo:
    def __init__(self):
        self.connection = {
            "access_token": "access",
            "refresh_token": "refresh",
            "calendar_id": "primary",
            "expires_at": None,
        }

    def get_private(self, user_id):
        return dict(self.connection)

    def upsert_tokens(
        self,
        *,
        user_id,
        values,
    ):
        self.connection.update(values)


class EventsRepo:
    def __init__(self):
        self.items = {}

    def list_for_user(self, user_id):
        return list(
            self.items.values()
        )

    def get_by_source(
        self,
        *,
        user_id,
        source_type,
        source_id,
    ):
        return self.items.get(
            (source_type, source_id)
        )

    def upsert_mapping(
        self,
        *,
        user_id,
        source_type,
        source_id,
        google_event_id,
        google_calendar_id,
    ):
        item = {
            "user_id": user_id,
            "source_type": source_type,
            "source_id": source_id,
            "google_event_id":
                google_event_id,
            "google_calendar_id":
                google_calendar_id,
        }

        self.items[
            (source_type, source_id)
        ] = item

        return item

    def delete_by_source(
        self,
        *,
        user_id,
        source_type,
        source_id,
    ):
        self.items.pop(
            (source_type, source_id),
            None,
        )


class PlannedRepo:
    def __init__(self):
        self.items = {
            "planned-1": {
                "id": "planned-1",
                "scheduled_date":
                    "2026-09-10",
                "scheduled_time":
                    "18:00:00",
                "title": "Corsa facile",
                "duration_minutes": 45,
                "notes": "Zona 2",
                "status": "planned",
            }
        }

    def list_range(
        self,
        user_id,
        start_date,
        end_date,
    ):
        return list(
            self.items.values()
        )

    def get(
        self,
        planned_id,
        user_id,
    ):
        return self.items.get(
            planned_id
        )


class StrengthRepo:
    def __init__(self):
        self.items = {
            "strength-1": {
                "id": "strength-1",
                "scheduled_date":
                    "2026-09-11",
                "title": "Upper body",
                "status": "planned",
                "estimated_duration_minutes":
                    60,
            }
        }

    def list_date_range(
        self,
        user_id,
        start_date,
        end_date,
    ):
        return list(
            self.items.values()
        )

    def get(
        self,
        user_id,
        workout_id,
    ):
        return self.items.get(
            workout_id
        )


class CalendarApi:
    def __init__(self):
        self.created = []
        self.updated = []
        self.deleted = []

    def create_event(
        self,
        *,
        access_token,
        calendar_id,
        event,
    ):
        event_id = (
            f"google-{len(self.created) + 1}"
        )

        self.created.append(
            {
                "id": event_id,
                "event": event,
            }
        )

        return {
            "id": event_id,
        }

    def update_event(
        self,
        *,
        access_token,
        calendar_id,
        event_id,
        event,
    ):
        self.updated.append(
            {
                "id": event_id,
                "event": event,
            }
        )

        return {
            "id": event_id,
        }

    def delete_event(
        self,
        *,
        access_token,
        calendar_id,
        event_id,
    ):
        self.deleted.append(
            event_id
        )


class OAuthService:
    def refresh_access_token(
        self,
        refresh_token,
    ):
        return {
            "access_token":
                "new-access",
            "refresh_token":
                refresh_token,
            "expires_at": None,
        }


def test_sync_create_update_delete_cycle():
    connections = ConnectionsRepo()
    events = EventsRepo()
    planned = PlannedRepo()
    strength = StrengthRepo()
    calendar = CalendarApi()

    service = GoogleCalendarSyncService(
        connections_repo=connections,
        events_repo=events,
        planned_repo=planned,
        strength_repo=strength,
        calendar_api=calendar,
        oauth_service=OAuthService(),
    )

    first = service.sync_range(
        user_id="user-1",
        start_date=date(
            2026, 9, 1
        ),
        end_date=date(
            2026, 9, 30
        ),
    )

    assert first == {
        "created": 2,
        "updated": 0,
        "deleted": 0,
    }

    assert len(
        calendar.created
    ) == 2

    assert len(
        events.items
    ) == 2

    planned.items[
        "planned-1"
    ]["title"] = "Corsa facile modificata"

    strength.items.clear()

    second = service.sync_range(
        user_id="user-1",
        start_date=date(
            2026, 9, 1
        ),
        end_date=date(
            2026, 9, 30
        ),
    )

    assert second == {
        "created": 0,
        "updated": 1,
        "deleted": 1,
    }

    assert (
        calendar.updated[-1]["event"][
            "summary"
        ]
        == "Corsa facile modificata"
    )

    assert len(
        calendar.deleted
    ) == 1

    planned.items.clear()

    third = service.sync_range(
        user_id="user-1",
        start_date=date(
            2026, 9, 1
        ),
        end_date=date(
            2026, 9, 30
        ),
    )

    assert third == {
        "created": 0,
        "updated": 0,
        "deleted": 1,
    }

    assert len(
        events.items
    ) == 0

    assert len(
        calendar.deleted
    ) == 2
