from __future__ import annotations


class NextMealReplanningService:
    """
    Identifica il prossimo momento alimentare non ancora
    registrato.

    Snack è il nome canonico corrente; Spuntino rimane
    supportato come alias per i dati storici.
    """

    SLOT_SEQUENCE = (
        ("breakfast", "Colazione"),
        ("lunch", "Pranzo"),
        ("snack", "Snack"),
        ("dinner", "Cena"),
    )

    MEAL_TYPE_ALIASES = {
        "spuntino": "Snack",
        "snack": "Snack",
    }

    @classmethod
    def normalize_meal_type(
        cls,
        meal_type: object,
    ) -> str:
        value = str(
            meal_type or ""
        ).strip()

        return cls.MEAL_TYPE_ALIASES.get(
            value.casefold(),
            value,
        )

    def next_slot(
        self,
        *,
        logged_meal_types: list[str],
    ) -> str | None:
        logged = {
            self.normalize_meal_type(
                meal_type
            )
            for meal_type in logged_meal_types
            if meal_type
        }

        for slot, meal_type in self.SLOT_SEQUENCE:
            if meal_type not in logged:
                return slot

        return None
