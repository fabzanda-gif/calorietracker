import requests
import pytest

pytestmark = pytest.mark.skip(reason="Legacy migration contract; Streamlit remains supported")

from pathlib import Path


def test_step4a_app_contains_fastapi_meals_bridge():
    text = Path("app.py").read_text(encoding="utf-8")

    assert "fetch_daily_meals_from_api" in text
    assert '"/meals/{cache_date}"' not in text  # f-string form expected
    assert "get_api_base_url" in text
    assert "auth_access_token" in text
    assert "MealsRepository(supabase).list_for_date_compatible" not in text
