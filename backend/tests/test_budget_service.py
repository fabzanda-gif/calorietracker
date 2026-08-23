import pytest

from backend.services.budget import BudgetInput, BudgetService


service = BudgetService()


def test_maintenance_budget_equals_bmr_plus_activity():
    result = service.calculate(
        BudgetInput(
            bmr=1800,
            activity_kcal=500,
            goal_mode="maintenance",
        )
    )

    assert result["maintenance_kcal"] == 2300
    assert result["daily_budget_kcal"] == 2300
    assert result["goal_adjustment_kcal"] == 0


def test_loss_subtracts_goal_adjustment():
    result = service.calculate(
        BudgetInput(
            bmr=1800,
            activity_kcal=500,
            goal_mode="loss",
            goal_adjustment_kcal=400,
        )
    )

    assert result["maintenance_kcal"] == 2300
    assert result["daily_budget_kcal"] == 1900


def test_gain_adds_goal_adjustment():
    result = service.calculate(
        BudgetInput(
            bmr=1800,
            activity_kcal=500,
            goal_mode="gain",
            goal_adjustment_kcal=300,
        )
    )

    assert result["daily_budget_kcal"] == 2600


def test_available_and_unallocated_are_distinct():
    result = service.calculate(
        BudgetInput(
            bmr=1800,
            activity_kcal=500,
            consumed_kcal=1100,
            planned_kcal=700,
            goal_mode="loss",
            goal_adjustment_kcal=400,
        )
    )

    assert result["daily_budget_kcal"] == 1900
    assert result["available_kcal"] == 800
    assert result["unallocated_kcal"] == 100


def test_available_can_be_negative():
    result = service.calculate(
        BudgetInput(
            bmr=1800,
            consumed_kcal=2000,
            goal_mode="maintenance",
        )
    )

    assert result["available_kcal"] == -200


def test_unallocated_can_be_negative_without_clamping():
    result = service.calculate(
        BudgetInput(
            bmr=1800,
            consumed_kcal=1000,
            planned_kcal=900,
            goal_mode="maintenance",
        )
    )

    assert result["available_kcal"] == 800
    assert result["unallocated_kcal"] == -100


def test_protein_remaining_is_calculated():
    result = service.calculate(
        BudgetInput(
            bmr=1800,
            protein_consumed_g=80,
            protein_target_g=140,
        )
    )

    assert result["protein_consumed_g"] == 80
    assert result["protein_target_g"] == 140
    assert result["protein_remaining_g"] == 60


def test_protein_remaining_never_goes_negative():
    result = service.calculate(
        BudgetInput(
            bmr=1800,
            protein_consumed_g=160,
            protein_target_g=140,
        )
    )

    assert result["protein_remaining_g"] == 0


def test_missing_protein_target_stays_unknown():
    result = service.calculate(
        BudgetInput(
            bmr=1800,
            protein_consumed_g=80,
            protein_target_g=None,
        )
    )

    assert result["protein_target_g"] is None
    assert result["protein_remaining_g"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("bmr", -1),
        ("activity_kcal", -1),
        ("consumed_kcal", -1),
        ("planned_kcal", -1),
        ("goal_adjustment_kcal", -1),
        ("protein_consumed_g", -1),
        ("protein_target_g", -1),
    ],
)
def test_negative_inputs_are_rejected(field, value):
    kwargs = {"bmr": 1800}
    kwargs[field] = value

    with pytest.raises(ValueError):
        service.calculate(BudgetInput(**kwargs))


def test_invalid_goal_mode_is_rejected():
    with pytest.raises(ValueError):
        service.calculate(
            BudgetInput(
                bmr=1800,
                goal_mode="cut",  # type: ignore[arg-type]
            )
        )


def test_fractional_values_are_preserved_with_rounding():
    result = service.calculate(
        BudgetInput(
            bmr=1800.55,
            activity_kcal=123.456,
            consumed_kcal=800.111,
            planned_kcal=400.222,
            goal_mode="gain",
            goal_adjustment_kcal=250.333,
        )
    )

    assert result["maintenance_kcal"] == 1924.01
    assert result["daily_budget_kcal"] == 2174.34
    assert result["available_kcal"] == 1374.23
    assert result["unallocated_kcal"] == 974.01
