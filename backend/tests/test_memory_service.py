from datetime import date

from backend.services.memory import MemoryService


class FakeDailyLogsRepository:
    def __init__(self, rows):
        self.rows = rows
        self.last_range = None

    def list_date_range(self, user_id, start_date, end_date, columns=None):
        self.last_range = (
            user_id,
            str(start_date),
            str(end_date),
        )
        return self.rows


def predict(rows, target="2026-09-01"):
    repo = FakeDailyLogsRepository(rows)
    service = MemoryService(repo)
    return service.predict_context(
        user_id="u1",
        day_date=date.fromisoformat(target),
    )


def test_no_history_is_unknown():
    result = predict([])

    assert result["state"] == "unknown"
    assert result["value"] is None
    assert result["evidence"] == {
        "observations": 0,
        "matches": 0,
    }


def test_one_observation_is_low_confidence():
    result = predict([
        {"date": "2026-08-25", "day_type": "Ufficio"},
    ])

    assert result["value"] == "Ufficio"
    assert result["confidence"] == 1.0
    assert result["confidence_level"] == "low"


def test_two_identical_observations_are_still_low_confidence():
    result = predict([
        {"date": "2026-08-18", "day_type": "Ufficio"},
        {"date": "2026-08-25", "day_type": "Ufficio"},
    ])

    assert result["confidence"] == 1.0
    assert result["confidence_level"] == "low"


def test_three_identical_observations_reach_medium_confidence():
    result = predict([
        {"date": "2026-08-11", "day_type": "Ufficio"},
        {"date": "2026-08-18", "day_type": "Ufficio"},
        {"date": "2026-08-25", "day_type": "Ufficio"},
    ])

    assert result["confidence_level"] == "medium"


def test_four_identical_observations_can_reach_high_confidence():
    result = predict([
        {"date": "2026-08-04", "day_type": "Ufficio"},
        {"date": "2026-08-11", "day_type": "Ufficio"},
        {"date": "2026-08-18", "day_type": "Ufficio"},
        {"date": "2026-08-25", "day_type": "Ufficio"},
    ])

    assert result["confidence"] == 1.0
    assert result["confidence_level"] == "high"
    assert result["evidence"] == {
        "observations": 4,
        "matches": 4,
    }


def test_three_office_one_home_is_not_high_confidence():
    result = predict([
        {"date": "2026-08-04", "day_type": "Casa"},
        {"date": "2026-08-11", "day_type": "Ufficio"},
        {"date": "2026-08-18", "day_type": "Ufficio"},
        {"date": "2026-08-25", "day_type": "Ufficio"},
    ])

    assert result["value"] == "Ufficio"
    assert result["confidence"] == 0.75
    assert result["confidence_level"] == "medium"


def test_only_same_weekday_is_considered():
    result = predict([
        {"date": "2026-08-24", "day_type": "Casa"},       # Monday
        {"date": "2026-08-25", "day_type": "Ufficio"},   # Tuesday
        {"date": "2026-08-19", "day_type": "Casa"},       # Wednesday
    ])

    assert result["value"] == "Ufficio"
    assert result["evidence"] == {
        "observations": 1,
        "matches": 1,
    }


def test_missing_day_type_is_ignored():
    result = predict([
        {"date": "2026-08-11", "day_type": None},
        {"date": "2026-08-18"},
        {"date": "2026-08-25", "day_type": "Ufficio"},
    ])

    assert result["value"] == "Ufficio"
    assert result["evidence"]["observations"] == 1
