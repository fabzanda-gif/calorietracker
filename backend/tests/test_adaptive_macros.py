from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.api.dependencies import CurrentUser
from backend.api.main import app
from backend.api.routers import adaptive_macros
from backend.services.adaptive_macros import AdaptiveMacroService


TODAY = date(2026, 11, 7)
START = TODAY - timedelta(days=27)
METADATA = {
    "gender": "male",
    "birth_date": "1995-04-10",
    "height": 178,
    "goal_mode": "loss",
    "goal_adjustment_kcal": 400,
    "protein_goal_enabled": True,
    "protein_goal_g": 140,
}


def weights(first=80.0, last=77.0):
    return [
        {"date": START.isoformat(), "weight": first},
        {"date": (START + timedelta(days=3)).isoformat(), "weight": first},
        {"date": (TODAY - timedelta(days=3)).isoformat(), "weight": last},
        {"date": TODAY.isoformat(), "weight": last},
    ]


def meals(days=28, calories=2100):
    return [
        {"date": (START + timedelta(days=offset)).isoformat(),
         "calories": calories, "protein": 140, "carbs": 215, "fat": 65}
        for offset in range(days)
    ]


def run_service(**kwargs):
    params = dict(
        as_of=TODAY,
        metadata=METADATA.copy(),
        weights=weights(),
        meals=meals(),
        activities=[],
        strength_logs=[],
    )
    params.update(kwargs)
    return AdaptiveMacroService().build(**params)


def test_loss_too_fast_proposes_small_deficit_reduction_only():
    result = run_service()
    assert result["status"] == "proposal_available"
    assert result["observed"]["logged_meal_days"] == 28
    assert result["observed"]["weight_measurements"] == 4
    assert result["observed"]["weight_change_pct_per_week"] < -0.9
    assert result["proposal"]["before_goal_adjustment_kcal"] == 400
    assert result["proposal"]["proposed_goal_adjustment_kcal"] == 300
    assert result["proposal"]["estimated_budget_change_kcal"] == 100
    assert result["proposal"]["requires_confirmation"] is True
    assert result["policy"]["auto_apply"] is False


def test_low_coverage_blocks_changes_despite_weight_trend():
    result = run_service(meals=meals(days=10))
    assert result["status"] == "insufficient_data"
    assert result["proposal"] is None
    assert any("20 giorni" in reason for reason in result["reasons"])


def test_missing_early_or_late_weights_blocks():
    result = run_service(weights=[
        {"date": (START + timedelta(days=14)).isoformat(), "weight": 80},
        {"date": (START + timedelta(days=16)).isoformat(), "weight": 80},
        {"date": (TODAY - timedelta(days=2)).isoformat(), "weight": 77},
        {"date": TODAY.isoformat(), "weight": 77},
    ])
    assert result["proposal"] is None
    assert any("prima" in reason for reason in result["reasons"])


def test_maintenance_does_not_invent_a_macro_change():
    result = run_service(metadata={**METADATA, "goal_mode": "maintenance"})
    assert result["proposal"] is None
    assert result["status"] == "maintenance_observation"


def test_gradual_gain_stall_proposes_small_surplus_increase():
    result = run_service(
        metadata={**METADATA, "goal_mode": "gain", "goal_adjustment_kcal": 250},
        weights=weights(first=80, last=80),
    )
    assert result["status"] == "proposal_available"
    assert result["proposal"]["proposed_goal_adjustment_kcal"] == 350
    assert result["proposal"]["estimated_budget_change_kcal"] == 100


def test_low_calorie_logs_cannot_increase_loss_deficit():
    result = run_service(
        weights=weights(first=80, last=80),
        meals=meals(calories=1100),
    )
    assert result["proposal"] is None
    assert any("basso" in reason for reason in result["reasons"])


def test_very_large_weight_change_requires_review():
    result = run_service(weights=weights(first=80, last=66))
    assert result["proposal"] is None
    assert any("insolita" in reason for reason in result["reasons"])


def test_missing_meals_are_not_assumed_zero_food():
    result = run_service(meals=[])
    assert result["observed"]["mean_logged_calories_kcal"] is None
    assert result["observed"]["logged_meal_days"] == 0
    assert result["proposal"] is None


def test_incomplete_profile_blocks_proposals_even_with_full_meals():
    result = run_service(metadata={
        "goal_mode": "loss", "goal_adjustment_kcal": 400,
        "protein_goal_enabled": False,
    })
    assert result["proposal"] is None
    assert result["observed"]["protein_target_g"] is None


def test_preview_digest_detects_logged_food_and_goal_changes():
    result = run_service()
    changed_meal = meals()
    changed_meal[0]["protein"] = 90
    assert run_service(meals=changed_meal)["preview_id"] != result["preview_id"]
    assert run_service(
        metadata={**METADATA, "goal_adjustment_kcal": 350}
    )["preview_id"] != result["preview_id"]


def test_training_context_only_uses_actual_sessions():
    result = run_service(
        activities=[
            {"date": "2026-11-05", "activity_type": "steps"},
            {"date": "2026-11-06", "activity_type": "running"},
        ],
        strength_logs=[
            {"performed_date": "2026-11-06", "status": "completed"},
            {"performed_date": "2026-11-04", "status": "draft"},
        ],
    )
    assert result["observed"]["training_days_with_meals"] == 1
    assert result["observed"]["non_training_days_with_meals"] == 27


class RangeRepo:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def history_range(self, owner, start, end):
        self.calls.append((owner, start, end))
        return self.results

    def list_date_range(self, owner, start, end, columns=None):
        self.calls.append((owner, start, end, columns))
        return self.results


def fixture_repos():
    return dict(
        meals_repo=RangeRepo(meals()),
        activities_repo=RangeRepo([]),
        strength_logs_repo=RangeRepo([]),
        weight_repo=RangeRepo(weights()),
    )


def identity(read_only=False):
    return CurrentUser(
        id="user-1", access_token="token",
        metadata=METADATA.copy(), read_only=read_only,
    )


def test_preview_endpoint_uses_authenticated_owner_for_all_queries():
    repos = fixture_repos()
    result = adaptive_macros.preview_adaptive_macros(
        as_of=TODAY, current_user=identity(), **repos,
    )
    assert result["proposal"] is not None
    assert "/adaptive-macros/preview" in app.openapi()["paths"]
    assert "/adaptive-macros/apply" in app.openapi()["paths"]
    assert all(
        repo.calls[0][0] == "user-1" for repo in repos.values()
    )


def test_apply_rejects_stale_snapshot_before_any_profile_write(monkeypatch):
    repos = fixture_repos()
    monkeypatch.setattr(
        adaptive_macros, "update_profile",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("No profile update expected")
        ),
    )
    with pytest.raises(HTTPException) as exc:
        adaptive_macros.apply_adaptive_macro_proposal(
            request=adaptive_macros.MacroApplyRequest(
                preview_id="0" * 64,
                confirm=True,
                logging_complete_confirmed=True,
            ),
            current_user=identity(),
            **repos,
        )
    assert exc.value.status_code == 409


def test_apply_read_only_account_never_reads_or_writes():
    class Forbidden:
        def __getattr__(self, name):
            raise AssertionError("Should not access repository")

    with pytest.raises(HTTPException) as exc:
        adaptive_macros.apply_adaptive_macro_proposal(
            request=adaptive_macros.MacroApplyRequest(
                preview_id="0" * 64,
                confirm=True,
                logging_complete_confirmed=True,
            ),
            current_user=identity(read_only=True),
            meals_repo=Forbidden(),
            activities_repo=Forbidden(),
            strength_logs_repo=Forbidden(),
            weight_repo=Forbidden(),
        )
    assert exc.value.status_code == 403


def test_apply_requires_explicit_double_confirmation():
    with pytest.raises(ValidationError):
        adaptive_macros.MacroApplyRequest(
            preview_id="a" * 64, confirm=False,
            logging_complete_confirmed=True,
        )
    with pytest.raises(ValidationError):
        adaptive_macros.MacroApplyRequest(
            preview_id="a" * 64, confirm=True,
            logging_complete_confirmed=False,
        )


def test_apply_recomputes_proposal_and_changes_only_goal_adjustment(monkeypatch):
    repos = fixture_repos()
    monkeypatch.setattr(adaptive_macros.date, "today", lambda: TODAY)
    # Revalidate the freshly built analysis; record only the metadata fields.
    preview = adaptive_macros.preview_adaptive_macros(
        as_of=TODAY, current_user=identity(), **fixture_repos(),
    )
    saved = []

    def profile_update(payload, *, current_user):
        saved.append(payload.model_dump(exclude_unset=True))
        assert current_user.id == "user-1"
        return {"id": "user-1", "metadata": saved[-1]}

    monkeypatch.setattr(adaptive_macros, "update_profile", profile_update)
    result = adaptive_macros.apply_adaptive_macro_proposal(
        request=adaptive_macros.MacroApplyRequest(
            preview_id=preview["preview_id"],
            confirm=True,
            logging_complete_confirmed=True,
        ),
        current_user=identity(),
        **repos,
    )
    assert result["applied"] is True
    assert saved == [
        {"goal_mode": "loss", "goal_adjustment_kcal": 300.0}
    ]
