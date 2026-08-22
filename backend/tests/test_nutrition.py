from datetime import date, datetime

import pytest

from backend.services.nutrition import (
    DEFICIT_PRESETS,
    calculate_age,
    calculate_bmr,
    calculate_recipe_totals,
    deficit_preset_from_value,
    deficit_preset_label,
    normalize_deficit_plan,
    parse_birth_date,
    resolve_deficit_target,
)


def test_parse_birth_date():
    assert parse_birth_date(None) is None
    assert parse_birth_date("") is None
    assert parse_birth_date("1990-05-20") == date(1990, 5, 20)
    assert parse_birth_date(datetime(1990, 5, 20, 12, 0)) == date(1990, 5, 20)
    assert parse_birth_date("not-a-date") is None


@pytest.mark.parametrize(
    ("birth", "on_date", "expected"),
    [
        ("1990-08-21", date(2026, 8, 21), 36),
        ("1990-08-22", date(2026, 8, 21), 35),
        ("2000-02-29", date(2026, 2, 28), 25),
        ("2000-02-29", date(2026, 3, 1), 26),
    ],
)
def test_calculate_age(birth, on_date, expected):
    assert calculate_age(birth, on_date) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("maintenance", "maintenance"),
        ("Mantenimento peso", "maintenance"),
        ("Weight maintenance", "maintenance"),
        ("Lento · 250 kcal", "slow"),
        ("Medium · 500 kcal", "medium"),
        ("Rapide · 750 kcal", "fast"),
        ("Custom", "custom"),
        ("nonsense", "custom"),
    ],
)
def test_normalize_deficit_plan(raw, expected):
    assert normalize_deficit_plan(raw) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "maintenance"),
        ("0", "maintenance"),
        (250, "slow"),
        (500.2, "medium"),
        (750, "fast"),
        (420, "custom"),
        (None, "custom"),
    ],
)
def test_deficit_preset_from_value(value, expected):
    assert deficit_preset_from_value(value) == expected


def test_resolve_deficit_target_manual_value_is_source_of_truth():
    assert resolve_deficit_target("fast", 420) == 420


def test_resolve_deficit_target_clamps_negative_manual_values():
    assert resolve_deficit_target("medium", -100) == 0


def test_resolve_deficit_target_uses_preset_when_manual_value_invalid():
    assert resolve_deficit_target("medium", None) == 500
    assert resolve_deficit_target("maintenance", "bad") == 0


def test_deficit_labels_are_framework_free_and_translated():
    assert deficit_preset_label(
        "maintenance",
        "Italiano",
    ) == "Mantenimento peso · 0 kcal"
    assert deficit_preset_label(
        "fast",
        "English",
    ) == "Fast · 750 kcal"


def test_calculate_bmr_male_is_deterministic():
    # Age = 36 on 2026-08-21.
    result = calculate_bmr(
        78.8,
        180,
        "1990-08-21",
        "Uomo",
        on_date=date(2026, 8, 21),
    )
    expected = round(
        (10 * 78.8)
        + (6.25 * 180)
        - (5 * 36)
        + 5
    )
    assert result == expected


def test_calculate_bmr_female_is_deterministic():
    result = calculate_bmr(
        65,
        168,
        "1990-08-21",
        "Donna",
        on_date=date(2026, 8, 21),
    )
    expected = round(
        (10 * 65)
        + (6.25 * 168)
        - (5 * 36)
        - 161
    )
    assert result == expected


def test_calculate_bmr_invalid_birth_date_returns_none():
    assert calculate_bmr(
        80,
        180,
        "invalid",
        "Uomo",
        on_date=date(2026, 8, 21),
    ) is None


def test_calculate_recipe_totals():
    ingredients = [
        {
            "name": "Riso",
            "quantity_g": 100,
            "calories_per_100g": 360,
            "protein_per_100g": 7,
            "carbs_per_100g": 80,
            "fat_per_100g": 1,
        },
        {
            "name": "Pollo",
            "quantity_g": 200,
            "calories_per_100g": 165,
            "protein_per_100g": 31,
            "carbs_per_100g": 0,
            "fat_per_100g": 3.6,
        },
    ]

    total_weight, totals, per100 = calculate_recipe_totals(
        ingredients
    )

    assert total_weight == pytest.approx(300)
    assert totals["calories"] == pytest.approx(690)
    assert totals["protein"] == pytest.approx(69)
    assert totals["carbs"] == pytest.approx(80)
    assert totals["fat"] == pytest.approx(8.2)

    assert per100["calories"] == pytest.approx(230)
    assert per100["protein"] == pytest.approx(23)
    assert per100["carbs"] == pytest.approx(80 / 3)
    assert per100["fat"] == pytest.approx(8.2 / 3)


def test_empty_recipe_totals_are_zero():
    total_weight, totals, per100 = calculate_recipe_totals([])
    assert total_weight == 0
    assert totals == {
        "calories": 0.0,
        "protein": 0.0,
        "carbs": 0.0,
        "fat": 0.0,
    }
    assert per100 == {
        "calories": 0,
        "protein": 0,
        "carbs": 0,
        "fat": 0,
    }
