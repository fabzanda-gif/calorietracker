from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from backend.services.training_load import TrainingLoadService


class CrossTrainingService:
    """Unified Gym ↔ Running timeline; advisory only, never edits a plan."""

    RUNNING = TrainingLoadService.RUNNING_TYPES
    HARD_RUNNING = {"hard", "race"}
    QUALITY_KINDS = {"tempo", "interval", "intervals", "long", "race"}

    @staticmethod
    def _day(raw: Any) -> date | None:
        try:
            return date.fromisoformat(str(raw)[:10])
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _running(item: dict) -> bool:
        return str(item.get("activity_type") or "").strip().casefold() in (
            CrossTrainingService.RUNNING
        )

    @staticmethod
    def _strength_scope(item: dict) -> str:
        focus = str(item.get("focus") or "").strip().casefold()
        if focus in {"upper", "push", "pull"}:
            return "upper"
        if focus in {"lower", "legs"}:
            return "lower"
        return "full_body"

    @staticmethod
    def _running_quality(item: dict) -> bool:
        kind = str(item.get("session_kind") or "").strip().casefold()
        intensity = str(item.get("intensity") or "").strip().casefold()
        return kind in CrossTrainingService.QUALITY_KINDS or intensity in (
            CrossTrainingService.HARD_RUNNING
        )

    def build(
        self, *,
        start_date: date,
        days: int = 14,
        planned_running: list[dict],
        planned_strength: list[dict],
        actual_activities: list[dict],
        completed_strength: list[dict],
        priority: str = "balanced",
    ) -> dict:
        if days < 1 or days > 21:
            raise ValueError("Cross-training window must be 1–21 days")
        if priority not in {"running", "gym", "balanced"}:
            priority = "balanced"
        end = start_date + timedelta(days=days - 1)
        events: list[dict] = []
        linked_running = {
            str(a["planned_activity_id"])
            for a in actual_activities if self._running(a)
            and a.get("planned_activity_id")
        }
        completed_gym_ids = {
            str(l["strength_workout_id"])
            for l in completed_strength if l.get("status") == "completed"
            and l.get("strength_workout_id")
        }
        load_service = TrainingLoadService()
        for item in actual_activities:
            if not self._running(item):
                continue
            day = self._day(item.get("date"))
            if not day or day < start_date or day > end or not item.get("id"):
                continue
            events.append({
                "id": "running:actual:" + str(item["id"]),
                "source_id": str(item["id"]),
                "date": day.isoformat(),
                "modality": "running",
                "status": "completed",
                "title": item.get("activity_name") or "Corsa",
                "scope": "lower",
                "quality": (
                    load_service._number(item.get("duration_seconds")) >= 3600
                    or load_service._number(item.get("distance_meters")) >= 10000
                ),
                "is_race": False,
            })
        for item in planned_running:
            if not self._running(item) or item.get("status") != "planned":
                continue
            day = self._day(item.get("scheduled_date"))
            if not day or not start_date <= day <= end or not item.get("id"):
                continue
            if str(item["id"]) in linked_running:
                continue
            kind = str(item.get("session_kind") or "").strip().casefold()
            events.append({
                "id": "running:planned:" + str(item["id"]),
                "source_id": str(item["id"]),
                "date": day.isoformat(),
                "modality": "running",
                "status": "planned",
                "title": item.get("title") or "Corsa prevista",
                "scope": "lower",
                "quality": self._running_quality(item),
                "is_race": kind == "race",
            })
        strength_metadata = {
            str(item["id"]): item
            for item in planned_strength if item.get("id")
        }
        for item in completed_strength:
            if item.get("status") != "completed" or not item.get("id"):
                continue
            day = self._day(item.get("performed_date"))
            if not day or not start_date <= day <= end:
                continue
            linked_workout = strength_metadata.get(
                str(item.get("strength_workout_id")), {}
            )
            events.append({
                "id": "strength:actual:" + str(item["id"]),
                "source_id": str(item["id"]),
                "date": day.isoformat(),
                "modality": "strength",
                "status": "completed",
                "title": linked_workout.get("title") or "Palestra completata",
                # Use known workout focus when present. Unknown strength
                # scope must not be misclassified as heavy leg training.
                "scope": (
                    self._strength_scope(linked_workout)
                    if linked_workout.get("focus") else "unknown"
                ),
                "quality": False,
                "is_race": False,
            })
        for item in planned_strength:
            if item.get("status") != "planned" or not item.get("id"):
                continue
            day = self._day(item.get("scheduled_date"))
            if not day or not start_date <= day <= end:
                continue
            if str(item["id"]) in completed_gym_ids:
                continue
            events.append({
                "id": "strength:planned:" + str(item["id"]),
                "source_id": str(item["id"]),
                "date": day.isoformat(),
                "modality": "strength",
                "status": "planned",
                "title": item.get("title") or "Palestra prevista",
                "scope": self._strength_scope(item),
                "quality": self._strength_scope(item) in {"lower", "full_body"},
                "is_race": False,
            })
        events.sort(key=lambda x: (x["date"], x["modality"], x["id"]))

        # Flag probable cross-modality collisions for human review. Do not
        # claim training readiness or calculate a clinical recovery score.
        conflicts: list[dict] = []
        for i, first in enumerate(events):
            for second in events[i+1:]:
                if first["modality"] == second["modality"]:
                    continue
                if first["status"] == second["status"] == "completed":
                    continue
                gap = abs((date.fromisoformat(first["date"]) -
                           date.fromisoformat(second["date"])).days)
                if gap > 2:
                    continue
                gym = first if first["modality"] == "strength" else second
                run = first if first["modality"] == "running" else second
                if gym["scope"] == "upper":
                    continue
                if gym["scope"] == "unknown":
                    continue
                if not run["quality"]:
                    continue
                if gap == 2 and not run["is_race"]:
                    continue
                severity = "high" if gap == 0 else "moderate"
                key = gym["id"] + "|" + run["id"]
                conflicts.append({
                    "id": key,
                    "date": max(gym["date"], run["date"]),
                    "severity": severity,
                    "gap_days": gap,
                    "gym_event_id": gym["id"],
                    "running_event_id": run["id"],
                    "race_protected": run["is_race"],
                    "message_key": (
                        "protect_race" if run["is_race"]
                        else "review_lower_and_quality_run"
                    ),
                    "requires_confirmation": True,
                    "suggested_action": (
                        "review_gym_schedule" if run["is_race"]
                        else "review_session_spacing"
                    ),
                })
        conflicts.sort(key=lambda x: (x["date"], x["id"]))
        by_day = defaultdict(list)
        for event in events:
            by_day[event["date"]].append(event)
        timeline = []
        for offset in range(days):
            day = (start_date + timedelta(days=offset)).isoformat()
            timeline.append({
                "date": day,
                "events": by_day[day],
                "running_count": sum(x["modality"] == "running" for x in by_day[day]),
                "strength_count": sum(x["modality"] == "strength" for x in by_day[day]),
            })
        return {
            "start_date": start_date.isoformat(),
            "end_date": end.isoformat(),
            "priority": priority,
            "timeline": timeline,
            "conflicts": conflicts,
            "summary": {
                "running_sessions": sum(x["modality"] == "running" for x in events),
                "strength_sessions": sum(x["modality"] == "strength" for x in events),
                "potential_conflicts": len(conflicts),
            },
            "policy": {
                "read_only": True,
                "auto_rescheduled": False,
                "auto_changed_load": False,
                "races_unchanged": True,
                "completed_workouts_unchanged": True,
            },
            "note": (
                "Coordinamento descrittivo: i conflitti sono segnali da valutare "
                "e non misure mediche di recupero. Nessun allenamento viene "
                "spostato o modificato automaticamente."
            ),
        }
