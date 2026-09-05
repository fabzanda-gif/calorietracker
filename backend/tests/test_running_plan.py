from datetime import date

import pytest

from backend.services.running_plan import (
    RunningPlanInput,
    build_running_plan,
)


def sample_plan(**overrides):
    values = {
        "start_date": date(2026, 9, 7),
        "target_date": date(2027, 3, 7),
        "current_distance_meters": 5000,
        "current_pace_seconds_per_km": 360,
        "target_distance_meters": 21100,
        "target_pace_seconds_per_km": 300,
        "sessions_per_week": 3,
        "long_run_weekday": 6,
    }
    values.update(overrides)
    return RunningPlanInput(**values)


def test_running_plan_builds_multiple_weeks():
    sessions = build_running_plan(
        sample_plan()
    )

    assert len(sessions) > 40
    assert sessions[0]["scheduled_date"] >= "2026-09-07"
    assert sessions[-1]["scheduled_date"] <= "2027-03-07"


def test_running_plan_finishes_with_target_race():
    sessions = build_running_plan(
        sample_plan()
    )

    final = sessions[-1]

    assert final["session_kind"] == "race"
    assert final["distance_meters"] == 21000
    assert final["intensity"] == "race"


def test_running_plan_contains_long_and_quality_sessions():
    sessions = build_running_plan(
        sample_plan()
    )

    kinds = {
        item["session_kind"]
        for item in sessions
    }

    assert "long" in kinds
    assert "tempo" in kinds or "interval" in kinds


def test_four_sessions_adds_recovery():
    sessions = build_running_plan(
        sample_plan(
            sessions_per_week=4
        )
    )

    assert any(
        item["session_kind"] == "recovery"
        for item in sessions
    )


def test_plan_shorter_than_eight_weeks_is_rejected():
    with pytest.raises(ValueError):
        build_running_plan(
            sample_plan(
                target_date=date(2026, 10, 1)
            )
        )
