from pathlib import Path
import pytest

pytestmark = pytest.mark.skip(reason="Legacy migration contract; Streamlit remains supported")


def test_step4c_app_contains_fastapi_activities_read_bridge():
    text = Path("app.py").read_text(encoding="utf-8")

    assert "fetch_daily_activities_from_api" in text
    assert "load_daily_activities_cached" in text
    assert "auth_access_token" in text

    assert 'f"{get_api_base_url()}/activities/{cache_date}"' in text

    assert (
        'supabase.table("activities")\n'
        '        .select("id,date,activity_name,burned_calories")'
        not in text
    )
