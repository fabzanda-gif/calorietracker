from backend.services.activity_movement_sync import (
    ActivityMovementSyncService,
)


class FakeDailyLogsRepository:
    def __init__(self, steps):
        self.steps = steps

    def get_for_date_compatible(
        self,
        user_id,
        day_date,
    ):
        return {
            "user_id": user_id,
            "date": str(day_date),
            "steps": self.steps,
        }


class FakeActivitiesRepository:
    def __init__(self, activities):
        self.activities = activities
        self.upsert = None
        self.deleted = None

    def list_for_date(
        self,
        user_id,
        day_date,
    ):
        return self.activities

    def delete_named_for_date(
        self,
        *,
        user_id,
        log_date,
        activity_name,
    ):
        self.deleted = {
            "user_id": user_id,
            "date": str(log_date),
            "activity_name": activity_name,
        }
        return True

    def upsert_named_for_date(
        self,
        user_id,
        log_date,
        activity_name,
        burned_calories,
    ):
        self.upsert = {
            "user_id": user_id,
            "date": str(log_date),
            "activity_name": activity_name,
            "burned_calories": burned_calories,
        }
        return {
            "id": "steps-activity",
            **self.upsert,
        }


def test_sync_preserves_raw_steps_and_offsets_training():
    daily_logs = FakeDailyLogsRepository(
        steps=12000
    )
    activities = FakeActivitiesRepository(
        [
            {
                "activity_name": "Corsa",
                "activity_type": "Corsa",
                "duration_seconds": 1800,
                "estimated_steps": 4950,
                "burned_calories": 325,
            },
            {
                "activity_name": "Padel",
                "activity_type": "Padel",
                "duration_seconds": 1200,
                "estimated_steps": 2100,
                "burned_calories": 167,
            },
        ]
    )

    result = ActivityMovementSyncService(
        activities_repo=activities,
        daily_logs_repo=daily_logs,
    ).sync(
        user_id="user-1",
        day_date="2026-09-01",
    )

    assert daily_logs.steps == 12000
    assert result["total_steps"] == 12000
    assert (
        result["estimated_training_steps"]
        == 7050
    )
    assert result["net_daily_steps"] == 4950
    assert result["step_calories"] == 198
    assert (
        activities.upsert["burned_calories"]
        == 198
    )


def test_sync_ignores_existing_step_activity():
    activities = FakeActivitiesRepository(
        [
            {
                "activity_name": "Passi (Stima)",
                "burned_calories": 999,
            }
        ]
    )

    result = ActivityMovementSyncService(
        activities_repo=activities,
        daily_logs_repo=FakeDailyLogsRepository(
            steps=5000
        ),
    ).sync(
        user_id="user-1",
        day_date="2026-09-01",
    )

    assert result["net_daily_steps"] == 5000
    assert result["step_calories"] == 200


def test_sync_caps_offset_at_total_steps():
    activities = FakeActivitiesRepository(
        [
            {
                "activity_name": "Corsa",
                "estimated_steps": 9000,
                "burned_calories": 600,
            }
        ]
    )

    result = ActivityMovementSyncService(
        activities_repo=activities,
        daily_logs_repo=FakeDailyLogsRepository(
            steps=3000
        ),
    ).sync(
        user_id="user-1",
        day_date="2026-09-01",
    )

    assert result["applied_step_offset"] == 3000
    assert result["net_daily_steps"] == 0
    assert result["step_calories"] == 0
    assert result["step_activity"] is None
    assert activities.upsert is None
    assert activities.deleted == {
        "user_id": "user-1",
        "date": "2026-09-01",
        "activity_name": "Passi (Stima)",
    }
