from pathlib import Path


def test_step4b_app_contains_fastapi_meals_crud_bridge():
    text = Path("app.py").read_text(encoding="utf-8")

    assert "create_meal_via_api" in text
    assert "update_meal_via_api" in text
    assert "delete_meal_via_api" in text

    assert "auth_access_token" in text
    assert "requests.post" in text
    assert "requests.patch" in text
    assert "requests.delete" in text

    assert "MealsRepository(supabase).create_compatible" not in text
    assert "MealsRepository(supabase).update" not in text
    assert "MealsRepository(supabase).delete" not in text


def test_step4b_meals_crud_uses_api_routes():
    text = Path("app.py").read_text(encoding="utf-8")

    assert 'f"{get_api_base_url()}/meals"' in text
    assert 'f"{get_api_base_url()}/meals/{meal_id}"' in text
