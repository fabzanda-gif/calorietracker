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
        adaptation_history: list[dict[str, Any]] | None = None,
    ) -> dict:
        history = adaptation_history or []
        source_id = str(
            source_session.get("id") or ""
        )

        if self._source_already_decided(
            source_id=source_id,
            history=history,
        ):
            return self._none(
                source_session=source_session,
                outcome=outcome,
                reason=(
                    "Hai già deciso come gestire questa "
                    "sessione. Non propongo lo stesso "
                    "adattamento una seconda volta."
                ),
            )

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

        target_id = str(
            target.get("id") or ""
        )

        if self._target_already_adapted(
            target_id=target_id,
            history=history,
        ):
            return self._none(
                source_session=source_session,
                outcome=outcome,
                reason=(
                    "La prossima sessione è già stata "
                    "adattata. Evito di correggerla due volte."
                ),
            )

        if self._too_many_consecutive_applied(
            history
        ):
            return self._none(
                source_session=source_session,
                outcome=outcome,
                reason=(
                    "Il piano è già stato adattato due volte "
                    "di seguito. Prima di ridurre ancora il "
                    "carico, serve osservare una nuova "
                    "sessione."
                ),
            )

        if self._target_is_in_race_lock(
            target=target,
            plan_sessions=plan_sessions,
        ):
            return self._none(
                source_session=source_session,
                outcome=outcome,
                reason=(
                    "Sei nella settimana finale prima della "
                    "gara. Il taper resta protetto e non viene "
                    "riscritto automaticamente."
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

    @staticmethod
    def _source_already_decided(
        *,
        source_id: str,
        history: list[dict[str, Any]],
    ) -> bool:
        if not source_id:
            return False

        return any(
            str(
                item.get(
                    "source_planned_activity_id"
                )
                or ""
            )
            == source_id
            and str(
                item.get("decision") or ""
            )
            in {"applied", "kept"}
            for item in history
        )

    @staticmethod
    def _target_already_adapted(
        *,
        target_id: str,
        history: list[dict[str, Any]],
    ) -> bool:
        if not target_id:
            return False

        return any(
            str(
                item.get(
                    "target_planned_activity_id"
                )
                or ""
            )
            == target_id
            and str(
                item.get("decision") or ""
            )
            == "applied"
            for item in history
        )

    @staticmethod
    def _too_many_consecutive_applied(
        history: list[dict[str, Any]],
    ) -> bool:
        consecutive = 0

        for item in history:
            decision = str(
                item.get("decision") or ""
            )

            if decision != "applied":
                break

            consecutive += 1

            if consecutive >= 2:
                return True

        return False

    @staticmethod
    def _target_is_in_race_lock(
        *,
        target: dict[str, Any],
        plan_sessions: list[dict[str, Any]],
    ) -> bool:
        from datetime import date

        target_value = str(
            target.get("scheduled_date") or ""
        )

        try:
            target_date = date.fromisoformat(
                target_value
            )
        except ValueError:
            return False

        race_dates = []

        for item in plan_sessions:
            if (
                str(
                    item.get("session_kind") or ""
                ).strip().lower()
                != "race"
            ):
                continue

            try:
                race_date = date.fromisoformat(
                    str(
                        item.get(
                            "scheduled_date"
                        )
                        or ""
                    )
                )
            except ValueError:
                continue

            if race_date >= target_date:
                race_dates.append(race_date)

        if not race_dates:
            return False

        next_race = min(race_dates)
        days_to_race = (
            next_race - target_date
        ).days

        return 0 <= days_to_race <= 7

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
