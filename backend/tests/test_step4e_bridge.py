from pathlib import Path
import pytest

pytestmark = pytest.mark.skip(reason="Legacy migration contract; Streamlit remains supported")


def test_step4e_recipes_bridge():
    text = Path("app.py").read_text(encoding="utf-8")

    assert "fetch_personal_recipes_from_api" in text
    assert "fetch_available_recipes_from_api" in text
    assert "fetch_shared_recipes_from_api" in text
    assert "fetch_recipe_by_id_from_api" in text

    assert "create_recipe_via_api" in text
    assert "update_recipe_via_api" in text
    assert "set_recipe_sharing_via_api" in text
    assert "delete_recipe_via_api" in text

    assert "RecipesRepository(" not in text


def test_step4e_recipes_routes():
    text = Path("app.py").read_text(encoding="utf-8")

    assert 'f"{get_api_base_url()}/recipes"' in text
    assert 'f"{get_api_base_url()}/recipes/available"' in text
    assert 'f"{get_api_base_url()}/recipes/shared"' in text
    assert 'f"{get_api_base_url()}/recipes/{recipe_id}"' in text
    assert 'f"{get_api_base_url()}/recipes/{recipe_id}/sharing"' in text


def test_step4e_uses_authenticated_api():
    text = Path("app.py").read_text(encoding="utf-8")

    assert "auth_access_token" in text
    assert "requests.get" in text
    assert "requests.post" in text
    assert "requests.patch" in text
    assert "requests.delete" in text
