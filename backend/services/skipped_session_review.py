from __future__ import annotations

from datetime import date, timedelta
from typing import Any


class SkippedSessionReviewService:
    """Suggest conservative recovery dates without changing any schedule."""

    @staticmethod
    def _date(value: Any) -> date | None:
        try:
            return date.fromisoformat(str(value or "")[:10])
        except ValueError:
            return None

    @staticmethod
    def _recovery_days(kind: str, session: dict[str, Any]) -> int:
        """Conservative scheduling heuristic, not a physiological score."""
        intensity = str(session.get("intensity") or "").strip().casefold()
        session_kind = str(session.get("session_kind") or "").strip().casefold()
        focus = str(session.get("focus") or "").strip().casefold()
        if intensity in {"hard", "high", "race"}:
            return 2
        if kind == "planned_activity" and session_kind in {
            "interval", "intervals", "tempo", "long", "race"
        }:
            return 2
        if kind == "strength_workout" and focus in {
            "lower", "legs", "full_body", "full body"
        }:
            return 2
        if intensity in {"low", "easy"} or session_kind in {
            "recovery", "easy"
        }:
            return 0
        return 1

    def build(
        self,
        *,
        as_of: date,
        running_sessions: list[dict[str, Any]],
        strength_workouts: list[dict[str, Any]],
        upcoming_running: list[dict[str, Any]] | None = None,
        upcoming_strength: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        calendar: list[tuple[date, int]] = []
        for kind, sessions in (
            ("planned_activity", upcoming_running or []),
            ("strength_workout", upcoming_strength or []),
        ):
            for session in sessions:
                if session.get("status") != "planned":
                    continue
                planned_date = self._date(session.get("scheduled_date"))
                if planned_date is not None:
                    calendar.append((
                        planned_date,
                        self._recovery_days(kind, session),
                    ))

        alerts: list[dict[str, Any]] = []
        reserved: list[tuple[date, int]] = []
        for kind, sessions in (
            ("planned_activity", running_sessions),
            ("strength_workout", strength_workouts),
        ):
            for session in sessions:
                if session.get("status") != "skipped":
                    continue
                scheduled_date = self._date(session.get("scheduled_date"))
                if scheduled_date is None or scheduled_date > as_of:
                    continue
                session_id = str(session.get("id") or "")
                if not session_id:
                    continue

                is_race = (
                    kind == "planned_activity"
                    and (
                        str(session.get("session_kind") or "").casefold() == "race"
                        or str(session.get("intensity") or "").casefold() == "race"
                    )
                )
                alerts.append({
                    "kind": kind,
                    "session_id": session_id,
                    "scheduled_date": scheduled_date.isoformat(),
                    "title": str(session.get("title") or "Allenamento"),
                    "is_race": is_race,
                    "recovery_days": self._recovery_days(kind, session),
                    "requires_approval": True,
                })

        alerts.sort(
            key=lambda item: (
                item["scheduled_date"],
                item["kind"],
                item["session_id"],
            )
        )

        for alert in alerts:
            suggested: date | None = None
            if not alert["is_race"]:
                for offset in range(1, 8):
                    candidate = as_of + timedelta(days=offset)
                    # Both sessions need enough time apart. Unknown
                    # load defaults to one full intervening day.
                    if any(
                        abs((candidate - day).days)
                        <= max(alert["recovery_days"], other_days)
                        for day, other_days in calendar + reserved
                    ):
                        continue
                    suggested = candidate
                    reserved.append((candidate, alert["recovery_days"]))
                    break

            alert["suggested_date"] = (
                suggested.isoformat() if suggested else None
            )
            if alert["is_race"]:
                alert["message"] = (
                    "Gara saltata: non viene ripianificata automaticamente. "
                    "Rivedi il piano prima di cambiare il calendario."
                )
            elif suggested:
                alert["message"] = (
                    "La seduta è stata saltata. Ho trovato una data libera "
                    "in base al carico previsto; conferma prima di spostarla."
                )
            else:
                alert["message"] = (
                    "La seduta è stata saltata. Non ho trovato una data "
                    "compatibile nei prossimi sette giorni."
                )

        return sorted(
            alerts,
            key=lambda item: (
                item["scheduled_date"],
                item["kind"],
                item["session_id"],
            ),
            reverse=True,
        )
