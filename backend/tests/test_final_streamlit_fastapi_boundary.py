from pathlib import Path


def test_streamlit_has_no_direct_domain_table_access():
    text = Path("app.py").read_text(encoding="utf-8")

    assert "supabase.table(" not in text

    assert "MealsRepository(" not in text
    assert "ActivitiesRepository(" not in text
    assert "WeightRepository(" not in text
    assert "DailyLogsRepository(" not in text
    assert "RecipesRepository(" not in text


def test_streamlit_keeps_only_allowed_supabase_services():
    text = Path("app.py").read_text(encoding="utf-8")

    assert "supabase.auth" in text
    assert "supabase.storage" in text
