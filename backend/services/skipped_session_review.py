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

    def build(
        self,
        *,
        as_of: date,
        running_sessions: list[dict[str, Any]],
        strength_workouts: list[dict[str, Any]],
        upcoming_running: list[dict[str, Any]] | None = None,
        upcoming_strength: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        occupied = {
            day
            for item in (upcoming_running or []) + (upcoming_strength or [])
            if item.get("status") == "planned"
            for day in [self._date(item.get("scheduled_date"))]
            if day is not None
        }
        alerts: list[dict[str, Any]] = []
        reserved: set[date] = set()

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
                # Allow a full day between the recovered workout and
                # any already planned workout, in either direction.
                for offset in range(1, 8):
                    candidate = as_of + timedelta(days=offset)
                    if any(
                        candidate + timedelta(days=delta) in occupied | reserved
                        for delta in (-1, 0, 1)
                    ):
                        continue
                    suggested = candidate
                    reserved.add(candidate)
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
                    "da valutare; il calendario cambia solo con la tua conferma."
                )
            else:
                alert["message"] = (
                    "La seduta è stata saltata. Non ho trovato una data libera "
                    "nei prossimi sette giorni: valuta il piano manualmente."
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
