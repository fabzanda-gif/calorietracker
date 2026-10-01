from pathlib import Path
import pytest

pytestmark = pytest.mark.skip(reason="Legacy migration contract; Streamlit remains supported")


def test_step4c_app_contains_fastapi_activities_crud_bridge():
    text = Path("app.py").read_text(encoding="utf-8")

    assert "fetch_daily_activities_from_api" in text
    assert "create_activity_via_api" in text
    assert "update_activity_via_api" in text
    assert "delete_activity_via_api" in text
    assert "upsert_named_activity_via_api" in text

    assert "requests.post" in text
    assert "requests.patch" in text
    assert "requests.delete" in text
    assert "auth_access_token" in text

    assert "ActivitiesRepository(supabase)" not in text
    assert "activities_repo" not in text


def test_step4c_activities_uses_api_routes():
    text = Path("app.py").read_text(encoding="utf-8")

    assert 'f"{get_api_base_url()}/activities/{cache_date}"' in text
    assert 'f"{get_api_base_url()}/activities"' in text
    assert 'f"{get_api_base_url()}/activities/{activity_id}"' in text
