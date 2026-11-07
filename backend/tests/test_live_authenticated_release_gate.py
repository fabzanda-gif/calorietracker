"""Real JWT SanoSync release gate (manual-run, NEVER production CI by default).

Unlike test_release_candidate_authenticated_journey.py this calls live
Supabase Auth and the deployed FastAPI instance with genuine JWTs.
With LIVE_E2E_MUTATIONS unset/false it performs only API reads and a
non-mutating program PREVIEW. The optional preference test restores
the account's prior state and MUST use dedicated disposable accounts.
"""
from __future__ import annotations

import os
from datetime import date
from urllib.parse import quote

import httpx
import pytest


REQUIRED = (
    "LIVE_E2E_SUPABASE_URL",
    "LIVE_E2E_SUPABASE_PUBLISHABLE_KEY",
    "LIVE_E2E_API_BASE_URL",
    "LIVE_E2E_USER_A_EMAIL",
    "LIVE_E2E_USER_A_PASSWORD",
    "LIVE_E2E_USER_B_EMAIL",
    "LIVE_E2E_USER_B_PASSWORD",
)
READY = all(os.getenv(key) for key in REQUIRED)
pytestmark = pytest.mark.skipif(
    not READY,
    reason="Manual authenticated gate: requires two dedicated JWT test accounts.",
)


def authenticate(email: str, password: str) -> tuple[str, str]:
    base = os.environ["LIVE_E2E_SUPABASE_URL"].rstrip("/")
    key = os.environ["LIVE_E2E_SUPABASE_PUBLISHABLE_KEY"]
    with httpx.Client(timeout=25) as client:
        response = client.post(
            base + "/auth/v1/token?grant_type=password",
            headers={"apikey": key, "Content-Type": "application/json"},
            json={"email": email, "password": password},
        )
    assert response.status_code == 200, (
        "Test account authentication failed; check confirmed email and API key. "
        f"HTTP {response.status_code}"
    )
    payload = response.json()
    assert payload.get("access_token") and payload.get("user", {}).get("id")
    return payload["access_token"], str(payload["user"]["id"])


def api(token: str, method: str, path: str, *, json: dict | None = None) -> httpx.Response:
    base = os.environ["LIVE_E2E_API_BASE_URL"].rstrip("/")
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        return client.request(
            method, base + path,
            headers={"Authorization": f"Bearer {token}"},
            json=json,
        )


@pytest.fixture(scope="module")
def live_identities():
    token_a, uid_a = authenticate(
        os.environ["LIVE_E2E_USER_A_EMAIL"],
        os.environ["LIVE_E2E_USER_A_PASSWORD"],
    )
    token_b, uid_b = authenticate(
        os.environ["LIVE_E2E_USER_B_EMAIL"],
        os.environ["LIVE_E2E_USER_B_PASSWORD"],
    )
    assert uid_a != uid_b, "Two different authenticated user IDs are mandatory."
    return (token_a, uid_a), (token_b, uid_b)


def test_authenticated_read_only_roadmap_journey(live_identities):
    today = date.today().isoformat()
    (a, _), (b, _) = live_identities
    paths = [
        "/onboarding/status",
        "/exercises/preferences",
        f"/athlete-state?as_of={today}",
        f"/training-nutrition/week?start_date={today}&days=1",
        f"/cross-training/timeline?start_date={today}&days=1",
        "/adaptive-macros/preview",
    ]
    for path in paths:
        for token in (a, b):
            response = api(token, "GET", path)
            assert response.status_code == 200, (
                f"Authenticated endpoint unavailable: {path}, "
                f"HTTP {response.status_code}: {response.text[:280]}"
            )
            assert isinstance(response.json(), dict)

    status = api(a, "GET", "/onboarding/status").json()
    assert "next_step" in status or "completed" in status

    preferences_a = api(a, "GET", "/exercises/preferences").json()
    preferences_b = api(b, "GET", "/exercises/preferences").json()
    assert isinstance(preferences_a.get("items"), list)
    assert isinstance(preferences_b.get("items"), list)

    athlete_a = api(a, "GET", f"/athlete-state?as_of={today}").json()
    athlete_b = api(b, "GET", f"/athlete-state?as_of={today}").json()
    assert athlete_a["last_28_days"]["completed_sessions"] >= 0
    assert athlete_b["last_28_days"]["completed_sessions"] >= 0

    for token in (a, b):
        context = api(
            token, "GET",
            f"/training-nutrition/week?start_date={today}&days=1",
        ).json()
        assert context["policy"]["read_only"] is True
        assert context["policy"]["calorie_target_changed"] is False
        cross = api(
            token, "GET",
            f"/cross-training/timeline?start_date={today}&days=1",
        ).json()
        assert cross["policy"]["read_only"] is True
        assert cross["policy"]["auto_rescheduled"] is False
        macro = api(token, "GET", "/adaptive-macros/preview").json()
        assert macro["policy"]["auto_apply"] is False

    # The generator preview is POST, but must never persist a plan.
    proposed = {
        "start_date": today, "goal": "hypertrophy",
        "total_weeks": 4, "allowed_equipment": ["dumbbell", "barbell"],
    }
    for token in (a, b):
        result = api(token, "POST", "/strength/plans/v2/preview", json=proposed)
        assert result.status_code in (200, 409, 422), (
            f"Unexpected generator response HTTP {result.status_code}: "
            f"{result.text[:280]}"
        )
        if result.status_code == 200:
            preview = result.json()
            assert preview["preview"] is True
            assert preview["generator_version"] == 2
            assert preview["ready_for_activation"] is False or (
                bool(preview["workouts"]) and
                all(e["approved_for_generation"] for w in preview["workouts"]
                    for e in w["exercises"])
            )


def test_missing_and_invalid_jwt_rejected():
    base = os.environ["LIVE_E2E_API_BASE_URL"].rstrip("/")
    with httpx.Client(timeout=30) as client:
        missing = client.get(base + "/onboarding/status")
        invalid = client.get(
            base + "/onboarding/status",
            headers={"Authorization": "Bearer invalid-e2e-token"},
        )
    assert missing.status_code == 401
    assert invalid.status_code == 401


def test_preference_owner_rls_with_cleanup(live_identities):
    if os.getenv("LIVE_E2E_MUTATIONS", "").lower() != "true":
        pytest.skip("Destructive-isolation checks require dedicated accounts and explicit LIVE_E2E_MUTATIONS=true.")

    (a, _), (b, _) = live_identities
    eid = os.environ.get("LIVE_E2E_EXERCISE_ID", "1435")
    id_url = quote(eid, safe="")
    path = f"/exercises/{id_url}/preference"

    before_a = api(a, "GET", "/exercises/preferences")
    before_b = api(b, "GET", "/exercises/preferences")
    assert before_a.status_code == 200 and before_b.status_code == 200

    # Use a fresh test-owned exercise. Prefer a source ID absent from B's
    # preferences, so detecting a cross-user leak remains unambiguous.
    from_a = {x["exercise_id"]: x["preference"] for x in before_a.json()["items"]}
    from_b = {x["exercise_id"]: x["preference"] for x in before_b.json()["items"]}
    catalog = api(a, "GET", f"/exercises/{id_url}")
    assert catalog.status_code == 200
    library_id = str(catalog.json()["id"])
    assert library_id not in from_b, (
        "Choose LIVE_E2E_EXERCISE_ID not already configured for user B."
    )
    previous = from_a.get(library_id)
    value = "excluded" if previous != "excluded" else "preferred"
    try:
        changed = api(a, "PUT", path, json={"preference": value})
        assert changed.status_code == 200, f"Own preference write failed: {changed.status_code}"
        visible_a = api(a, "GET", "/exercises/preferences")
        visible_b = api(b, "GET", "/exercises/preferences")
        assert any(
            x["exercise_id"] == library_id and x["preference"] == value
            for x in visible_a.json()["items"]
        )
        assert all(
            x["exercise_id"] != library_id
            for x in visible_b.json()["items"]
        ), "Cross-account RLS violation: user A preference visible to B."
    finally:
        restored = (
            api(a, "PUT", path, json={"preference": previous})
            if previous else api(a, "DELETE", path)
        )
        assert restored.status_code in (200, 204), (
            "CRITICAL: preference cleanup failed; manual review required."
        )


def test_demo_mutations_blocked_if_demo_test_account_configured():
    email = os.getenv("LIVE_E2E_DEMO_EMAIL")
    password = os.getenv("LIVE_E2E_DEMO_PASSWORD")
    if not email or not password:
        pytest.skip("Demo credentials not configured.")
    token, _ = authenticate(email, password)
    response = api(token, "PUT", "/onboarding/training", json={
        "experience_level": "beginner",
        "sessions_per_week": 2,
        "session_duration_minutes": 60,
        "planning_horizon": "weekly",
        "schedule_flexibility": "flexible",
    })
    assert response.status_code == 403, (
        "Demo unexpectedly accepted profile mutation: "
        f"HTTP {response.status_code}"
    )
