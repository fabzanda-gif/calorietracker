from __future__ import annotations

from typing import Any


class RunningPlanAdaptationService:
    """
    Build one deterministic adaptation proposal from the
    outcome of a completed/skipped planned session.

    The service does not persist anything.
    """

    QUALITY_KINDS = {
        "tempo",
        "interval",
        "intervals",
        "long",
    }

    def build(
        self,
        *,
        source_session: dict[str, Any],
        outcome: dict[str, Any],
        plan_sessions: list[dict[str, Any]],
    ) -> dict:
        action = str(
            outcome.get("recommended_action") or ""
        ).strip().lower()

        outcome_kind = str(
            outcome.get("outcome") or ""
        ).strip().lower()

        if action in {"keep_plan", "review", ""}:
            return self._none(
                source_session=source_session,
                outcome=outcome,
                reason=(
                    "Il risultato non richiede una modifica "
                    "automatica del piano."
                ),
            )

        target = self._next_quality_session(
            source_session=source_session,
            plan_sessions=plan_sessions,
        )

        if target is None:
            return self._none(
                source_session=source_session,
                outcome=outcome,
                reason=(
                    "Non ci sono sessioni di qualità future "
                    "adatte da modificare."
                ),
            )

        if outcome_kind == "skipped":
            reduction = 0.15
        elif action == "recover_next":
            reduction = 0.15
        else:
            reduction = 0.10

        changes = self._changes(
            target=target,
            reduction=reduction,
            recover=(action == "recover_next"),
        )

        if not changes:
            return self._none(
                source_session=source_session,
                outcome=outcome,
                reason=(
                    "La prossima sessione non contiene volume "
                    "sufficiente per un adattamento utile."
                ),
            )

        if action == "recover_next":
            title = "Proteggi il recupero"
            message = (
                "Hai fatto più carico del previsto. "
                "Propongo di ridurre del 15% la prossima "
                "sessione di qualità e di non mantenerla "
                "su intensità hard."
            )
        elif outcome_kind == "skipped":
            title = "Riparti senza recuperare tutto insieme"
            message = (
                "La sessione precedente è stata saltata. "
                "Propongo una riduzione del 15% della "
                "prossima sessione di qualità."
            )
        else:
            title = "Consolida prima di aumentare"
            message = (
                "Hai fatto meno carico del previsto. "
                "Propongo una riduzione del 10% della "
                "prossima sessione di qualità."
            )

        return {
            "adaptation_required": True,
            "source_planned_activity_id": (
                source_session.get("id")
            ),
            "training_plan_id": source_session.get(
                "training_plan_id"
            ),
            "outcome": outcome_kind,
            "recommended_action": action,
            "title": title,
            "message": message,
            "target": self._snapshot(target),
            "changes": changes,
            "preview": self._apply_preview(
                target,
                changes,
            ),
        }

    def _next_quality_session(
        self,
        *,
        source_session: dict[str, Any],
        plan_sessions: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        source_date = str(
            source_session.get("scheduled_date") or ""
        )

        future = [
            item
            for item in plan_sessions
            if (
                str(item.get("status") or "planned")
                == "planned"
                and str(
                    item.get("scheduled_date") or ""
                ) > source_date
                and str(
                    item.get("session_kind") or ""
                ).strip().lower()
                in self.QUALITY_KINDS
            )
        ]

        future.sort(
            key=lambda item: (
                str(item.get("scheduled_date") or ""),
                str(item.get("scheduled_time") or ""),
            )
        )

        return future[0] if future else None

    def _changes(
        self,
        *,
        target: dict[str, Any],
        reduction: float,
        recover: bool,
    ) -> dict[str, Any]:
        changes: dict[str, Any] = {}

        distance = self._number(
            target.get("distance_meters")
        )

        duration = self._number(
            target.get("duration_minutes")
        )

        if distance > 0:
            changes["distance_meters"] = round(
                distance * (1.0 - reduction),
                0,
            )

        if duration > 0:
            changes["duration_minutes"] = max(
                1,
                round(
                    duration * (1.0 - reduction)
                ),
            )

        intensity = str(
            target.get("intensity") or ""
        ).strip().lower()

        if recover and intensity in {
            "hard",
            "race",
        }:
            changes["intensity"] = "moderate"

        return changes

    @staticmethod
    def _snapshot(
        session: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "id": session.get("id"),
            "scheduled_date": session.get(
                "scheduled_date"
            ),
            "scheduled_time": session.get(
                "scheduled_time"
            ),
            "title": session.get("title"),
            "session_kind": session.get(
                "session_kind"
            ),
            "training_week": session.get(
                "training_week"
            ),
            "distance_meters": session.get(
                "distance_meters"
            ),
            "duration_minutes": session.get(
                "duration_minutes"
            ),
            "intensity": session.get(
                "intensity"
            ),
        }

    def _apply_preview(
        self,
        target: dict[str, Any],
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        result = self._snapshot(target)
        result.update(changes)
        return result

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return max(
                0.0,
                float(value or 0),
            )
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _none(
        *,
        source_session: dict[str, Any],
        outcome: dict[str, Any],
        reason: str,
    ) -> dict:
        return {
            "adaptation_required": False,
            "source_planned_activity_id": (
                source_session.get("id")
            ),
            "training_plan_id": source_session.get(
                "training_plan_id"
            ),
            "outcome": outcome.get("outcome"),
            "recommended_action": outcome.get(
                "recommended_action"
            ),
            "title": "Nessun adattamento necessario",
            "message": reason,
            "target": None,
            "changes": {},
            "preview": None,
        }
