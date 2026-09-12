from __future__ import annotations

from typing import Any


class PlannedActivityOutcomeService:
    """
    Compare one planned training session with the most
    compatible actual activity recorded on the same day.

    This service only produces an adaptation signal.
    It deliberately does NOT mutate the training plan.
    """

    RUNNING_TYPES = {
        "corsa",
        "running",
        "run",
    }

    def build(
        self,
        *,
        planned: dict[str, Any],
        actual_activities: list[dict[str, Any]],
    ) -> dict:
        status = str(
            planned.get("status") or "planned"
        ).strip().lower()

        if status == "skipped":
            return self._result(
                planned=planned,
                actual=None,
                outcome="skipped",
                action="ease_next",
                message=(
                    "Sessione saltata. Non serve recuperarla "
                    "tutta insieme: meglio proteggere la "
                    "continuità del piano."
                ),
            )

        actual = self._best_match(
            planned=planned,
            activities=actual_activities,
        )

        if actual is None:
            return self._result(
                planned=planned,
                actual=None,
                outcome="unmatched",
                action="review",
                message=(
                    "Non trovo un'attività reale abbastanza "
                    "compatibile con questa sessione."
                ),
            )

        load_ratio = self._load_ratio(
            planned=planned,
            actual=actual,
        )

        if load_ratio is None:
            return self._result(
                planned=planned,
                actual=actual,
                outcome="on_target",
                action="keep_plan",
                message=(
                    "Allenamento registrato. Mancano però "
                    "dati sufficienti per confrontare il "
                    "carico con precisione."
                ),
                load_ratio=None,
            )

        if load_ratio < 0.80:
            return self._result(
                planned=planned,
                actual=actual,
                outcome="under",
                action="ease_next",
                message=(
                    "Hai completato sensibilmente meno carico "
                    "del previsto. Il prossimo lavoro intenso "
                    "non dovrebbe aumentare."
                ),
                load_ratio=load_ratio,
            )

        if load_ratio > 1.20:
            return self._result(
                planned=planned,
                actual=actual,
                outcome="over",
                action="recover_next",
                message=(
                    "Hai fatto sensibilmente più carico del "
                    "previsto. Conviene proteggere il recupero "
                    "prima del prossimo lavoro impegnativo."
                ),
                load_ratio=load_ratio,
            )

        return self._result(
            planned=planned,
            actual=actual,
            outcome="on_target",
            action="keep_plan",
            message=(
                "Carico vicino a quello previsto. Il piano "
                "può proseguire senza correzioni."
            ),
            load_ratio=load_ratio,
        )

    def _best_match(
        self,
        *,
        planned: dict[str, Any],
        activities: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        planned_date = str(
            planned.get("scheduled_date") or ""
        )

        planned_type = self._normalized_type(
            planned.get("activity_type")
        )

        candidates = [
            item
            for item in activities
            if str(item.get("date") or "") == planned_date
        ]

        if planned_type in self.RUNNING_TYPES:
            candidates = [
                item
                for item in candidates
                if self._normalized_type(
                    item.get("activity_type")
                    or item.get("activity_name")
                )
                in self.RUNNING_TYPES
            ]

        if not candidates:
            return None

        return min(
            candidates,
            key=lambda item: self._match_distance(
                planned,
                item,
            ),
        )

    def _match_distance(
        self,
        planned: dict[str, Any],
        actual: dict[str, Any],
    ) -> float:
        planned_distance = self._number(
            planned.get("distance_meters")
        )
        actual_distance = self._number(
            actual.get("distance_meters")
        )

        if (
            planned_distance > 0
            and actual_distance > 0
        ):
            return abs(
                actual_distance - planned_distance
            ) / planned_distance

        planned_duration = self._number(
            planned.get("duration_minutes")
        )
        actual_duration = (
            self._number(
                actual.get("duration_seconds")
            )
            / 60.0
        )

        if (
            planned_duration > 0
            and actual_duration > 0
        ):
            return abs(
                actual_duration - planned_duration
            ) / planned_duration

        return 1.0

    def _load_ratio(
        self,
        *,
        planned: dict[str, Any],
        actual: dict[str, Any],
    ) -> float | None:
        planned_distance = self._number(
            planned.get("distance_meters")
        )
        actual_distance = self._number(
            actual.get("distance_meters")
        )

        if (
            planned_distance > 0
            and actual_distance > 0
        ):
            return actual_distance / planned_distance

        planned_duration = self._number(
            planned.get("duration_minutes")
        )
        actual_duration = (
            self._number(
                actual.get("duration_seconds")
            )
            / 60.0
        )

        if (
            planned_duration > 0
            and actual_duration > 0
        ):
            return actual_duration / planned_duration

        return None

    @classmethod
    def _normalized_type(
        cls,
        value: Any,
    ) -> str:
        return " ".join(
            str(value or "")
            .strip()
            .casefold()
            .replace("_", " ")
            .split()
        )

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return max(
                0.0,
                float(value or 0),
            )
        except (TypeError, ValueError):
            return 0.0

    def _result(
        self,
        *,
        planned: dict[str, Any],
        actual: dict[str, Any] | None,
        outcome: str,
        action: str,
        message: str,
        load_ratio: float | None = None,
    ) -> dict:
        planned_distance = self._number(
            planned.get("distance_meters")
        )
        planned_duration = self._number(
            planned.get("duration_minutes")
        )

        actual_distance = (
            self._number(
                actual.get("distance_meters")
            )
            if actual is not None
            else 0.0
        )

        actual_duration = (
            self._number(
                actual.get("duration_seconds")
            )
            / 60.0
            if actual is not None
            else 0.0
        )

        return {
            "planned_activity_id": planned.get("id"),
            "training_plan_id": planned.get(
                "training_plan_id"
            ),
            "training_week": planned.get(
                "training_week"
            ),
            "session_kind": planned.get(
                "session_kind"
            ),
            "outcome": outcome,
            "recommended_action": action,
            "message": message,
            "load_ratio": (
                round(load_ratio, 3)
                if load_ratio is not None
                else None
            ),
            "planned": {
                "distance_meters": planned_distance,
                "duration_minutes": planned_duration,
            },
            "actual": (
                {
                    "id": actual.get("id"),
                    "activity_name": actual.get(
                        "activity_name"
                    ),
                    "distance_meters": actual_distance,
                    "duration_minutes": round(
                        actual_duration,
                        2,
                    ),
                    "burned_calories": self._number(
                        actual.get(
                            "burned_calories"
                        )
                    ),
                }
                if actual is not None
                else None
            ),
        }
