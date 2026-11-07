from __future__ import annotations

from datetime import date
from typing import Any


class SkippedSessionReviewService:
    """Surface missed sessions for review; never reschedule automatically."""

    def build(
        self,
        *,
        as_of: date,
        running_sessions: list[dict[str, Any]],
        strength_workouts: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        alerts: list[dict[str, str]] = []

        for kind, sessions in (
            ("planned_activity", running_sessions),
            ("strength_workout", strength_workouts),
        ):
            for session in sessions:
                if session.get("status") != "skipped":
                    continue

                scheduled = str(session.get("scheduled_date") or "")
                try:
                    scheduled_date = date.fromisoformat(scheduled[:10])
                except ValueError:
                    continue

                if scheduled_date > as_of:
                    continue

                title = str(session.get("title") or "Allenamento")
                is_race = (
                    kind == "planned_activity"
                    and (
                        str(session.get("session_kind") or "").casefold() == "race"
                        or str(session.get("intensity") or "").casefold() == "race"
                    )
                )
                message = (
                    "La gara risulta saltata. Valuta il programma con il coach "
                    "prima di cambiare le altre sedute."
                    if is_race
                    else (
                        "Questa seduta è stata saltata. Controlla il calendario "
                        "e scegli se ripianificarla o mantenere il recupero."
                    )
                )

                alerts.append({
                    "kind": kind,
                    "session_id": str(session.get("id") or ""),
                    "scheduled_date": scheduled_date.isoformat(),
                    "title": title,
                    "message": message,
                    "requires_approval": True,
                })

        return sorted(
            alerts,
            key=lambda item: (
                item["scheduled_date"],
                item["kind"],
                item["session_id"],
            ),
            reverse=True,
        )
