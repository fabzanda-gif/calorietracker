from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.api.dependencies import CurrentUser
from backend.api.routers import days


@pytest.mark.parametrize("read_only", [True, False])
def test_briefing_generation_persists_only_for_writable_users(monkeypatch, read_only):
    days._DAY_BRIEFING_CACHE.clear()
    monkeypatch.setattr(days, "_build_day", lambda **kwargs: {})
    monkeypatch.setattr(days, "_build_budget", lambda **kwargs: {})
    monkeypatch.setattr(days, "_planned_repo_from_activities", lambda repo: None)
    monkeypatch.setattr(days.DayBriefingService, "generate", lambda *args, **kwargs: "Briefing")
    briefing_repo = SimpleNamespace(get=Mock(return_value=None), save=Mock())

    response = days.get_day_briefing(
        day_date=date(2026, 11, 8), moment="evening", mode="standard",
        hour=18, language="it",
        current_user=CurrentUser(id="source", access_token="token", read_only=read_only),
        daily_logs_repo=object(), weekly_schedule_repo=object(),
        meals_repo=SimpleNamespace(list_for_date_compatible=lambda *args: []),
        activities_repo=SimpleNamespace(list_for_date=lambda *args: []),
        weight_repo=SimpleNamespace(latest=lambda *args: None),
        briefing_repo=briefing_repo,
    )
    assert response["message"] == "Briefing"
    assert briefing_repo.save.call_count == (0 if read_only else 1)
    days._DAY_BRIEFING_CACHE.clear()
