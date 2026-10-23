from __future__ import annotations

from typing import Any

from backend.repositories.activities import (
    ActivitiesRepository,
)
from backend.repositories.daily_logs import (
    DailyLogsRepository,
)
from backend.services.activity_movement import (
    movement_step_summary,
)


class ActivityMovementSyncService:
    """
    Sincronizza le calorie attribuite al movimento quotidiano.

    daily_logs.steps conserva sempre il numero grezzo originale.
    La riga Passi (Stima) contiene soltanto le calorie dei passi
    rimasti dopo l'offset degli allenamenti.
    """

    STEP_ACTIVITY_NAME = "Passi (Stima)"

    def __init__(
        self,
        *,
        activities_repo: ActivitiesRepository,
        daily_logs_repo: DailyLogsRepository,
    ) -> None:
        self.activities_repo = activities_repo
        self.daily_logs_repo = daily_logs_repo

    def sync(
        self,
        *,
        user_id: str,
        day_date: Any,
    ) -> dict:
        daily_log = (
            self.daily_logs_repo
            .get_for_date_compatible(
                user_id,
                day_date,
            )
        )

        total_steps = (
            daily_log.get("steps")
            if daily_log
            else 0
        )

        activities = (
            self.activities_repo.list_for_date(
                user_id,
                day_date,
            )
        )

        summary = movement_step_summary(
            total_steps=total_steps,
            activities=activities,
        )

        if summary["net_daily_steps"] <= 0:
            self.activities_repo.delete_named_for_date(
                user_id=user_id,
                log_date=day_date,
                activity_name=self.STEP_ACTIVITY_NAME,
            )
            step_activity = None
        else:
            step_activity = (
                self.activities_repo
                .upsert_named_for_date(
                    user_id=user_id,
                    log_date=day_date,
                    activity_name=self.STEP_ACTIVITY_NAME,
                    burned_calories=int(
                        summary["step_calories"]
                    ),
                )
            )

        return {
            **summary,
            "step_activity": step_activity,
        }
