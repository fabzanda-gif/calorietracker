from backend.services.meal_replanning_context import (
    MealReplanningContextService,
)


service = MealReplanningContextService()


def test_reduced_portion_with_consumed_food_explains_food_pressure():
    result = service.build(
        recommendation={
            "strategy": "adapted_routine",
            "portion_multiplier": 0.75,
        },
        actual={
            "consumed_kcal": 1200,
            "actual_activity_kcal": 0,
        },
        budget={
            "available_kcal": 500,
        },
    )

    assert result == {
        "direction": "reduced",
        "driver": "food",
        "portion_changed": True,
        "available_kcal": 500,
        "title": "Porzione adattata alla giornata",
        "message": (
            "Quello che hai già registrato oggi lascia "
            "meno margine per questo pasto."
        ),
    }


def test_activity_is_exposed_as_positive_budget_context():
    result = service.build(
        recommendation={
            "strategy": "routine",
            "portion_multiplier": 1.0,
        },
        actual={
            "consumed_kcal": 1200,
            "actual_activity_kcal": 500,
        },
        budget={
            "available_kcal": 900,
        },
    )

    assert result == {
        "direction": "expanded",
        "driver": "activity",
        "portion_changed": False,
        "available_kcal": 900,
        "title": "Più margine disponibile",
        "message": (
            "L'attività registrata oggi ha aumentato "
            "il margine disponibile."
        ),
    }


def test_normal_day_has_neutral_context():
    result = service.build(
        recommendation={
            "strategy": "routine",
            "portion_multiplier": 1.0,
        },
        actual={
            "consumed_kcal": 300,
            "actual_activity_kcal": 0,
        },
        budget={
            "available_kcal": 1400,
        },
    )

    assert result == {
        "direction": "unchanged",
        "driver": "normal",
        "portion_changed": False,
        "available_kcal": 1400,
        "title": "In linea con la giornata",
        "message": (
            "Il pasto abituale è compatibile con "
            "il margine disponibile."
        ),
    }


def test_missing_recommendation_returns_none():
    result = service.build(
        recommendation=None,
        actual={
            "consumed_kcal": 300,
            "actual_activity_kcal": 0,
        },
        budget={
            "available_kcal": 1400,
        },
    )

    assert result is None

def test_removed_component_has_explicit_context():
    result = service.build(
        recommendation={
            "strategy": "component_reduction",
            "portion_multiplier": 1.0,
            "adaptation": {
                "changed": True,
                "type": "component_removal",
                "removed_components": [
                    {
                        "name": "Mela",
                        "calories": 95,
                    }
                ],
            },
        },
        actual={
            "consumed_kcal": 900,
            "actual_activity_kcal": 0,
        },
        budget={
            "available_kcal": 500,
        },
    )

    assert result == {
        "direction": "reduced",
        "driver": "food",
        "portion_changed": False,
        "available_kcal": 500,
        "title": "Pasto alleggerito, porzioni invariate",
        "message": (
            "Rimuovo Mela e mantengo invariato "
            "il piatto principale."
        ),
        "removed_components": ["Mela"],
    }
