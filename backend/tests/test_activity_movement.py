from backend.services.activity_movement import (
    activity_profile,
    estimated_activity_steps,
    movement_step_summary,
    suggested_activity_calories,
)


def test_profiles_supply_dropdown_defaults():
    profile = activity_profile("Padel")

    assert profile["activity_type"] == "Padel"
    assert profile["icon"] == "🎾"
    assert profile["step_cadence"] == 105


def test_activity_calories_scale_with_duration():
    assert suggested_activity_calories(
        activity_type="Padel",
        duration_seconds=3600,
    ) == 500

    assert suggested_activity_calories(
        activity_type="Padel",
        duration_seconds=1800,
    ) == 250


def test_padel_steps_are_estimated_from_duration():
    assert estimated_activity_steps(
        activity_type="Padel",
        duration_seconds=3600,
    ) == 6300


def test_running_single_leg_cadence_is_normalized():
    assert estimated_activity_steps(
        activity_type="Corsa",
        duration_seconds=3600,
        average_cadence=81,
    ) == 9720


def test_non_step_activity_has_no_offset():
    assert estimated_activity_steps(
        activity_type="Nuoto",
        duration_seconds=3600,
    ) == 0

    assert estimated_activity_steps(
        activity_type="Palestra",
        duration_seconds=3600,
    ) == 0


def test_step_summary_avoids_double_counting():
    result = movement_step_summary(
        total_steps=12000,
        activities=[
            {
                "activity_name": "Corsa serale",
                "activity_type": "Corsa",
                "duration_seconds": 1800,
            },
            {
                "activity_name": "Padel",
                "activity_type": "Padel",
                "duration_seconds": 1200,
            },
        ],
    )

    # Corsa: 4.950, Padel: 2.100.
    assert (
        result["estimated_training_steps"]
        == 7050
    )
    assert result["net_daily_steps"] == 4950
    assert result["step_calories"] == 198


def test_offset_never_makes_steps_negative():
    result = movement_step_summary(
        total_steps=3000,
        activities=[
            {
                "activity_name": "Corsa",
                "activity_type": "Corsa",
                "duration_seconds": 3600,
            }
        ],
    )

    assert result["applied_step_offset"] == 3000
    assert result["net_daily_steps"] == 0
    assert result["step_calories"] == 0


def test_existing_step_activity_is_not_offset_again():
    result = movement_step_summary(
        total_steps=8000,
        activities=[
            {
                "activity_name": "Passi (Stima)",
                "duration_seconds": 9999,
                "estimated_steps": 9999,
            }
        ],
    )

    assert result["estimated_training_steps"] == 0
    assert result["net_daily_steps"] == 8000
