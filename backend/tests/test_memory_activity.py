from datetime import date

from backend.services.memory import MemoryService


class FakeDailyLogsRepository:
    def __init__(self, rows):
        self.rows = rows

    def list_date_range(self, user_id, start_date, end_date, columns=None):
        return self.rows


def predict_activity(rows, target="2026-09-01"):
    service = MemoryService(FakeDailyLogsRepository(rows))
    return service.predict_activity_plan(
        user_id="u1",
        day_date=date.fromisoformat(target),
    )


def test_activity_without_history_is_unknown():
    result = predict_activity([])

    assert result["state"] == "unknown"
    assert result["value"] is None


def test_one_activity_observation_is_low_confidence():
    result = predict_activity([
        {"date": "2026-08-25", "activity_plan": "Attiva"},
    ])

    assert result["value"] == "Attiva"
    assert result["confidence"] == 1.0
    assert result["confidence_level"] == "low"


def test_four_identical_activity_observations_are_high_confidence():
    result = predict_activity([
        {"date": "2026-08-04", "activity_plan": "Attiva"},
        {"date": "2026-08-11", "activity_plan": "Attiva"},
        {"date": "2026-08-18", "activity_plan": "Attiva"},
        {"date": "2026-08-25", "activity_plan": "Attiva"},
    ])

    assert result["value"] == "Attiva"
    assert result["confidence_level"] == "high"
    assert result["evidence"]["recent_matches"] == 4


def test_activity_uses_only_same_weekday():
    result = predict_activity([
        {"date": "2026-08-24", "activity_plan": "Riposo"},
        {"date": "2026-08-25", "activity_plan": "Attiva"},
        {"date": "2026-08-19", "activity_plan": "Riposo"},
    ])

    assert result["value"] == "Attiva"
    assert result["evidence"]["observations"] == 1


def test_missing_activity_plan_is_ignored():
    result = predict_activity([
        {"date": "2026-08-11", "activity_plan": None},
        {"date": "2026-08-18"},
        {"date": "2026-08-25", "activity_plan": "Moderatamente attiva"},
    ])

    assert result["value"] == "Moderatamente attiva"
    assert result["evidence"]["observations"] == 1


def test_single_recent_activity_change_does_not_rewrite_routine():
    rows = [
        {"date": "2026-06-16", "activity_plan": "Attiva"},
        {"date": "2026-06-23", "activity_plan": "Attiva"},
        {"date": "2026-06-30", "activity_plan": "Attiva"},
        {"date": "2026-07-07", "activity_plan": "Attiva"},
        {"date": "2026-07-14", "activity_plan": "Attiva"},
        {"date": "2026-07-21", "activity_plan": "Attiva"},
        {"date": "2026-07-28", "activity_plan": "Attiva"},
        {"date": "2026-08-04", "activity_plan": "Attiva"},
        {"date": "2026-08-11", "activity_plan": "Attiva"},
        {"date": "2026-08-18", "activity_plan": "Attiva"},
        {"date": "2026-08-25", "activity_plan": "Riposo"},
    ]

    result = predict_activity(rows)

    assert result["value"] == "Attiva"
    assert result["evidence"]["change_detected"] is False


def test_four_recent_activity_changes_override_old_pattern():
    rows = [
        {"date": "2026-05-26", "activity_plan": "Attiva"},
        {"date": "2026-06-02", "activity_plan": "Attiva"},
        {"date": "2026-06-09", "activity_plan": "Attiva"},
        {"date": "2026-06-16", "activity_plan": "Attiva"},
        {"date": "2026-06-23", "activity_plan": "Attiva"},
        {"date": "2026-06-30", "activity_plan": "Attiva"},
        {"date": "2026-07-07", "activity_plan": "Attiva"},
        {"date": "2026-07-14", "activity_plan": "Attiva"},
        {"date": "2026-07-21", "activity_plan": "Attiva"},
        {"date": "2026-07-28", "activity_plan": "Attiva"},
        {"date": "2026-08-04", "activity_plan": "Riposo"},
        {"date": "2026-08-11", "activity_plan": "Riposo"},
        {"date": "2026-08-18", "activity_plan": "Riposo"},
        {"date": "2026-08-25", "activity_plan": "Riposo"},
    ]

    result = predict_activity(rows)

    assert result["value"] == "Riposo"
    assert result["confidence_level"] == "high"
    assert result["evidence"]["change_detected"] is True
