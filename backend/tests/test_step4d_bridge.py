from pathlib import Path
import pytest

pytestmark = pytest.mark.skip(reason="Legacy migration contract; Streamlit remains supported")


def test_step4d_daily_logs_bridge():
    text = Path("app.py").read_text(encoding="utf-8")

    assert "fetch_daily_log_from_api" in text
    assert "update_daily_log_via_api" in text

    assert 'f"{get_api_base_url()}/daily-logs/{cache_date}"' in text
    assert 'f"{get_api_base_url()}/daily-logs/{log_date}"' in text

    assert "DailyLogsRepository(" not in text


def test_step4d_weight_bridge():
    text = Path("app.py").read_text(encoding="utf-8")

    assert "fetch_weight_history_from_api" in text
    assert "create_weight_via_api" in text
    assert "update_weight_via_api" in text
    assert "delete_weight_via_api" in text

    assert 'f"{get_api_base_url()}/weight"' in text
    assert 'f"{get_api_base_url()}/weight/{row_id}"' in text

    assert "WeightRepository(supabase)" not in text
    assert "weight_repo." not in text


def test_step4d_uses_authenticated_api():
    text = Path("app.py").read_text(encoding="utf-8")

    assert "auth_access_token" in text
    assert "requests.get" in text
    assert "requests.post" in text
    assert "requests.patch" in text
    assert "requests.delete" in text
