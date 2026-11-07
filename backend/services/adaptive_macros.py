from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from hashlib import sha256
from json import dumps
from math import isfinite
from statistics import median
from typing import Any, Mapping

from backend.services.profile_goal import ProfileGoalService


class AdaptiveMacroService:
    """Conservative, explainable, non-automatic nutrition goal proposals.

    This is a trend estimator, not an energy expenditure estimator.
    Missing meal logs are never interpreted as zero intake.
    """

    LOOKBACK_DAYS = 28
    MIN_LOGGED_DAYS = 20
    MIN_WEIGHT_POINTS = 4
    MAX_CHANGE_KCAL = 100.0

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            result = float(value)
            return result if isfinite(result) else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _date(value: Any) -> date | None:
        try:
            return date.fromisoformat(str(value)[:10])
        except (TypeError, ValueError):
            return None

    def build(
        self,
        *,
        as_of: date,
        metadata: Mapping[str, Any],
        weights: list[dict],
        meals: list[dict],
        activities: list[dict],
        strength_logs: list[dict],
    ) -> dict:
        start = as_of - timedelta(days=self.LOOKBACK_DAYS - 1)
        points_by_day: dict[date, float] = {}
        for item in weights:
            day = self._date(item.get("date"))
            value = self._number(item.get("weight"))
            if (
                day is not None and start <= day <= as_of
                and value is not None and 35 <= value <= 350
            ):
                points_by_day[day] = value
        points = sorted(points_by_day.items())
        latest_weight = points[-1][1] if points else None

        meals_by_day = defaultdict(list)
        for item in meals:
            day = self._date(item.get("date"))
            if day is not None and start <= day <= as_of:
                meals_by_day[day].append(item)
        totals = []
        for day, entries in sorted(meals_by_day.items()):
            totals.append({
                "date": day.isoformat(),
                "meal_count": len(entries),
                "calories_kcal": round(sum(max(0, self._number(x.get("calories")) or 0) for x in entries), 1),
                "protein_g": round(sum(max(0, self._number(x.get("protein")) or 0) for x in entries), 1),
                "carbs_g": round(sum(max(0, self._number(x.get("carbs")) or 0) for x in entries), 1),
                "fat_g": round(sum(max(0, self._number(x.get("fat")) or 0) for x in entries), 1),
            })
        profile = ProfileGoalService().build(
            metadata,
            current_weight=latest_weight,
            on_date=as_of,
        )
        mode = profile["goal_mode"]
        adjustment = profile["goal_adjustment_kcal"]
        protein_target = profile["protein_target_g"]
        reasons: list[str] = []
        if len(points) < self.MIN_WEIGHT_POINTS:
            reasons.append("Servono almeno quattro pesate valide negli ultimi 28 giorni.")
        early = [(d, w) for d, w in points if d <= start + timedelta(days=6)]
        late = [(d, w) for d, w in points if d >= as_of - timedelta(days=6)]
        if len(early) < 2 or len(late) < 2:
            reasons.append("Servono almeno due pesate nella prima e nell'ultima settimana.")
        if points and (points[-1][0] - points[0][0]).days < 21:
            reasons.append("Le pesate devono coprire almeno 21 giorni.")
        if len(totals) < self.MIN_LOGGED_DAYS:
            reasons.append("Servono almeno 20 giorni con pasti registrati negli ultimi 28.")
        last_applied = self._date(metadata.get("adaptive_macros_last_applied_on"))
        if last_applied is not None and 0 <= (as_of - last_applied).days < 14:
            reasons.append(
                "Adattamento recente: osserva almeno 14 giorni prima di una nuova proposta."
            )
        if mode == "maintenance":
            reasons.append("Per il mantenimento osserviamo il trend senza modificare l'obiettivo calorico.")
        if mode in {"gain", "loss"} and adjustment <= 0:
            reasons.append("Configura prima un surplus o deficit esplicito nel profilo.")
        if not profile["profile_complete_for_budget"]:
            reasons.append("Il profilo nutrizionale non è completo per stimare il budget.")
        weight_rate = None
        if len(early) >= 2 and len(late) >= 2:
            first = median(w for _, w in early)
            last = median(w for _, w in late)
            elapsed = (median([d.toordinal() for d, _ in late])
                       - median([d.toordinal() for d, _ in early]))
            if elapsed > 0 and first > 0:
                weight_rate = round((last - first) / first * 100 * 7 / elapsed, 3)
                if abs(weight_rate) > 2:
                    reasons.append(
                        "Variazione di peso insolita: verifica le misurazioni prima di adattare gli obiettivi."
                    )

        training_days = set()
        for item in activities:
            day = self._date(item.get("date"))
            if day is not None and start <= day <= as_of:
                kind = str(item.get("activity_type") or "").strip().casefold()
                if kind not in {"steps", "passi", "walking steps"}:
                    training_days.add(day)
        for item in strength_logs:
            day = self._date(item.get("performed_date"))
            if item.get("status") == "completed" and day and start <= day <= as_of:
                training_days.add(day)
        logged_training = [x for x in totals if self._date(x["date"]) in training_days]
        logged_other = [x for x in totals if self._date(x["date"]) not in training_days]

        def average(values: list[dict], field: str) -> float | None:
            return (round(sum(x[field] for x in values) / len(values), 1)
                    if values else None)

        observed = {
            "logged_meal_days": len(totals),
            "weight_measurements": len(points),
            "weight_observation_span_days": (
                (points[-1][0] - points[0][0]).days if len(points) >= 2 else 0
            ),
            "weight_change_pct_per_week": weight_rate,
            "training_days_with_meals": len(logged_training),
            "non_training_days_with_meals": len(logged_other),
            "mean_logged_calories_kcal": average(totals, "calories_kcal"),
            "mean_logged_protein_g": average(totals, "protein_g"),
            "mean_training_day_carbs_g": average(logged_training, "carbs_g"),
            "mean_other_day_carbs_g": average(logged_other, "carbs_g"),
            "protein_target_g": protein_target,
        }

        proposal = None
        if not reasons and weight_rate is not None:
            # Broad guard bands; differences inside are noise, not a signal
            # to change an energy budget. Change magnitudes <=100 kcal/day.
            direction = 0
            if mode == "loss":
                if weight_rate < -0.9:
                    direction = -1  # smaller deficit
                elif weight_rate > -0.15:
                    direction = 1   # larger deficit
            elif mode == "gain":
                if weight_rate > 0.5:
                    direction = -1  # smaller surplus
                elif weight_rate < 0.05:
                    direction = 1   # larger surplus
            # A smaller observed intake may be incomplete logging. Never
            # propose a stronger loss deficit on a low reported mean.
            if (
                direction > 0 and mode == "loss"
                and observed["mean_logged_calories_kcal"] is not None
                and observed["mean_logged_calories_kcal"] < 1500
            ):
                reasons.append(
                    "Introito registrato basso: evita di aumentare il deficit senza verifica professionale."
                )
                direction = 0
            if direction:
                new_adjustment = max(0.0, min(750.0, adjustment + direction * self.MAX_CHANGE_KCAL))
                if new_adjustment != adjustment:
                    proposal = {
                        "kind": "adjust_goal_energy",
                        "goal_mode": mode,
                        "before_goal_adjustment_kcal": round(adjustment, 1),
                        "proposed_goal_adjustment_kcal": round(new_adjustment, 1),
                        "estimated_budget_change_kcal": round(
                            (-1 if mode == "loss" else 1) * (new_adjustment - adjustment), 1
                        ),
                        "requires_confirmation": True,
                        "reason": "Trend ponderale osservato per almeno tre settimane con registrazioni alimentari sufficienti.",
                    }

        status = (
            "insufficient_data" if reasons and mode != "maintenance"
            else "maintenance_observation" if mode == "maintenance"
            else "proposal_available" if proposal else "within_range"
        )
        result: dict[str, Any] = {
            "as_of": as_of.isoformat(),
            "start_date": start.isoformat(),
            "lookback_days": self.LOOKBACK_DAYS,
            "goal_mode": mode,
            "current_goal_adjustment_kcal": round(adjustment, 1),
            "status": status,
            "reasons": reasons,
            "observed": observed,
            "proposal": proposal,
            "policy": {
                "auto_apply": False,
                "missing_meals_are_not_zero_intake": True,
                "no_unverified_macro_targets": True,
                "max_adjustment_step_kcal": self.MAX_CHANGE_KCAL,
            },
        }
        # A deterministic digest allows the apply endpoint to re-read all
        # data and reject stale previews. It confers no authorization by itself.
        fingerprint = {
            "as_of": result["as_of"], "goal_mode": mode,
            "adjustment": adjustment, "observed": observed,
            "proposal": proposal, "status": status,
            "protein_configured": metadata.get("protein_goal_enabled"),
            "last_adapted": metadata.get("adaptive_macros_last_applied_on"),
            "raw_weights": [
                (day.isoformat(), value) for day, value in points
            ],
            "daily_food": totals,
            "training_days": sorted(d.isoformat() for d in training_days),
        }
        result["preview_id"] = sha256(
            dumps(fingerprint, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        return result
