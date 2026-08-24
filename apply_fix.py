from pathlib import Path

path = Path("backend/tests/test_api_ranked_meal_options_modes.py")
text = path.read_text(encoding="utf-8")

old = '''def test_out_mode_is_empty_until_restaurant_sources_exist():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "out"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_count"] == 0
    assert payload["empty_reason"] == "no_known_eating_out_options"
'''

new = '''def test_out_mode_uses_generic_fallback_without_history():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "out"},
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["candidate_count"] == 3
    assert payload["known_eating_out_count"] == 0
    assert payload["generic_eating_out_count"] == 3
    assert payload["empty_reason"] is None

    assert all(
        item["source"] == "generic_eating_out"
        for item in payload["candidates"]
    )
'''

if old not in text:
    raise SystemExit(
        "Expected test block not found. No changes made."
    )

path.write_text(
    text.replace(old, new, 1),
    encoding="utf-8",
)

print("Updated:", path)
