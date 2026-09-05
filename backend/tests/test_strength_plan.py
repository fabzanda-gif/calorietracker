from datetime import date

import pytest

from backend.services.strength_plan import (
    StrengthPlanInput,
    StrengthPlanService,
)


def build(
    *,
    sessions=3,
    goal="hypertrophy",
    level="intermediate",
    weeks=8,
):
    return StrengthPlanService().build(
        StrengthPlanInput(
            start_date=date(2026, 9, 7),
            goal=goal,
            experience_level=level,
            sessions_per_week=sessions,
            total_weeks=weeks,
        )
    )


def test_two_days_generates_full_body_ab():
    result = build(
        sessions=2,
        weeks=4,
    )

    assert result["program_style"] == "full_body"
    assert result["workout_count"] == 8

    first_week = result["workouts"][:2]

    assert [
        item["title"]
        for item in first_week
    ] == [
        "Full Body A",
        "Full Body B",
    ]

    assert all(
        item["focus"] == "full_body"
        for item in first_week
    )


def test_three_days_generates_full_body_abc():
    result = build(
        sessions=3,
        weeks=4,
    )

    assert result["workout_count"] == 12

    assert [
        item["title"]
        for item in result["workouts"][:3]
    ] == [
        "Full Body A",
        "Full Body B",
        "Full Body C",
    ]


def test_four_days_generates_upper_lower():
    result = build(
        sessions=4,
        weeks=4,
    )

    assert result["program_style"] == "upper_lower"
    assert result["workout_count"] == 16

    first_week = result["workouts"][:4]

    assert [
        item["focus"]
        for item in first_week
    ] == [
        "upper",
        "lower",
        "upper",
        "lower",
    ]


def test_dates_are_deterministic_and_ordered():
    result = build(
        sessions=3,
        weeks=4,
    )

    first_week = result["workouts"][:3]

    assert [
        item["scheduled_date"]
        for item in first_week
    ] == [
        "2026-09-07",
        "2026-09-09",
        "2026-09-11",
    ]

    dates = [
        item["scheduled_date"]
        for item in result["workouts"]
    ]

    assert dates == sorted(dates)


def test_every_workout_has_valid_exercises():
    result = build(
        sessions=4,
        weeks=4,
    )

    for workout in result["workouts"]:
        assert workout["exercises"]

        positions = [
            item["position"]
            for item in workout["exercises"]
        ]

        assert positions == list(
            range(
                1,
                len(positions) + 1,
            )
        )

        for exercise in workout["exercises"]:
            assert exercise["target_sets"] > 0
            assert (
                exercise["target_reps_max"]
                >= exercise[
                    "target_reps_min"
                ]
            )
            assert (
                exercise["prescribed_load_kg"]
                is None
            )


def test_strength_goal_uses_lower_rep_range():
    result = build(
        sessions=2,
        goal="strength",
        weeks=4,
    )

    primary = (
        result["workouts"][0]
        ["exercises"][0]
    )

    assert primary["target_reps_min"] == 4
    assert primary["target_reps_max"] == 6
    assert primary["rest_seconds"] == 180


def test_hypertrophy_accessory_uses_higher_reps():
    result = build(
        sessions=2,
        goal="hypertrophy",
        weeks=4,
    )

    accessory = (
        result["workouts"][0]
        ["exercises"][4]
    )

    assert accessory["target_reps_min"] == 10
    assert accessory["target_reps_max"] == 15


def test_beginner_keeps_more_reps_in_reserve():
    beginner = build(
        sessions=2,
        goal="strength",
        level="beginner",
        weeks=4,
    )

    intermediate = build(
        sessions=2,
        goal="strength",
        level="intermediate",
        weeks=4,
    )

    beginner_primary = (
        beginner["workouts"][0]
        ["exercises"][0]
    )

    intermediate_primary = (
        intermediate["workouts"][0]
        ["exercises"][0]
    )

    assert beginner_primary["target_rir"] == 3.0
    assert intermediate_primary["target_rir"] == 2.0


def test_advanced_can_train_closer_to_failure():
    result = build(
        sessions=2,
        goal="hypertrophy",
        level="advanced",
        weeks=4,
    )

    primary = (
        result["workouts"][0]
        ["exercises"][0]
    )

    assert primary["target_rir"] == 1.0


@pytest.mark.parametrize(
    "sessions",
    [1, 5, 6],
)
def test_v1_rejects_unsupported_frequency(
    sessions,
):
    with pytest.raises(
        ValueError,
        match="2, 3 or 4",
    ):
        build(
            sessions=sessions,
            weeks=4,
        )


def test_generator_is_deterministic():
    first = build(
        sessions=4,
        goal="general_fitness",
        weeks=4,
    )

    second = build(
        sessions=4,
        goal="general_fitness",
        weeks=4,
    )

    assert first == second
