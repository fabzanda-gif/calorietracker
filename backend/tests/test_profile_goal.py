from datetime import date

from backend.services.profile_goal import ProfileGoalService


service = ProfileGoalService()
ON_DATE = date(2026, 8, 25)


BASE_META = {
    "height": 180,
    "birth_date": "1990-01-01",
    "gender": "Uomo",
}


def test_legacy_deficit_maps_to_loss():
    result = service.build(
        {
            **BASE_META,
            "deficit_plan": "medium",
            "deficit_target_kcal": 500,
        },
        current_weight=80,
        on_date=ON_DATE,
    )

    assert result["goal_mode"] == "loss"
    assert result["goal_adjustment_kcal"] == 500
    assert result["bmr"] is not None


def test_legacy_maintenance_maps_to_maintenance():
    result = service.build(
        {
            **BASE_META,
            "deficit_plan": "maintenance",
            "deficit_target_kcal": 0,
        },
        current_weight=80,
        on_date=ON_DATE,
    )

    assert result["goal_mode"] == "maintenance"
    assert result["goal_adjustment_kcal"] == 0


def test_zero_legacy_deficit_is_maintenance_even_if_plan_is_custom():
    result = service.build(
        {
            **BASE_META,
            "deficit_plan": "custom",
            "deficit_target_kcal": 0,
        },
        current_weight=80,
        on_date=ON_DATE,
    )

    assert result["goal_mode"] == "maintenance"


def test_new_goal_mode_overrides_legacy_fields():
    result = service.build(
        {
            **BASE_META,
            "goal_mode": "gain",
            "goal_adjustment_kcal": 300,
            "deficit_plan": "fast",
            "deficit_target_kcal": 750,
        },
        current_weight=80,
        on_date=ON_DATE,
    )

    assert result["goal_mode"] == "gain"
    assert result["goal_adjustment_kcal"] == 300


def test_new_maintenance_forces_zero_adjustment():
    result = service.build(
        {
            **BASE_META,
            "goal_mode": "maintenance",
            "goal_adjustment_kcal": 500,
        },
        current_weight=80,
        on_date=ON_DATE,
    )

    assert result["goal_mode"] == "maintenance"
    assert result["goal_adjustment_kcal"] == 0


def test_explicit_loss_mode_is_supported():
    result = service.build(
        {
            **BASE_META,
            "goal_mode": "loss",
            "goal_adjustment_kcal": 420,
        },
        current_weight=80,
        on_date=ON_DATE,
    )

    assert result["goal_mode"] == "loss"
    assert result["goal_adjustment_kcal"] == 420


def test_protein_goal_is_exposed_when_enabled():
    result = service.build(
        {
            **BASE_META,
            "protein_goal_enabled": True,
            "protein_goal_g": 160,
        },
        current_weight=80,
        on_date=ON_DATE,
    )

    assert result["protein_target_g"] == 160


def test_disabled_protein_goal_stays_unknown():
    result = service.build(
        {
            **BASE_META,
            "protein_goal_enabled": False,
            "protein_goal_g": 160,
        },
        current_weight=80,
        on_date=ON_DATE,
    )

    assert result["protein_target_g"] is None


def test_missing_protein_goal_stays_unknown():
    result = service.build(
        BASE_META,
        current_weight=80,
        on_date=ON_DATE,
    )

    assert result["protein_target_g"] is None


def test_bmr_uses_current_weight_not_target_weight():
    low_weight = service.build(
        {
            **BASE_META,
            "target_weight": 60,
        },
        current_weight=80,
        on_date=ON_DATE,
    )

    higher_weight = service.build(
        {
            **BASE_META,
            "target_weight": 60,
        },
        current_weight=90,
        on_date=ON_DATE,
    )

    assert higher_weight["bmr"] > low_weight["bmr"]


def test_missing_current_weight_marks_profile_incomplete():
    result = service.build(
        BASE_META,
        current_weight=None,
        on_date=ON_DATE,
    )

    assert result["bmr"] is None
    assert result["profile_complete_for_budget"] is False


def test_missing_height_marks_profile_incomplete():
    result = service.build(
        {
            "birth_date": "1990-01-01",
            "gender": "Uomo",
        },
        current_weight=80,
        on_date=ON_DATE,
    )

    assert result["bmr"] is None
    assert result["profile_complete_for_budget"] is False


def test_invalid_birth_date_marks_profile_incomplete():
    result = service.build(
        {
            "height": 180,
            "birth_date": "not-a-date",
            "gender": "Uomo",
        },
        current_weight=80,
        on_date=ON_DATE,
    )

    assert result["bmr"] is None


def test_negative_explicit_adjustment_is_clamped_to_zero():
    result = service.build(
        {
            **BASE_META,
            "goal_mode": "gain",
            "goal_adjustment_kcal": -300,
        },
        current_weight=80,
        on_date=ON_DATE,
    )

    assert result["goal_mode"] == "gain"
    assert result["goal_adjustment_kcal"] == 0
