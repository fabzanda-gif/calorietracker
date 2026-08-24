from pathlib import Path

path = Path("backend/tests/test_api_eating_out_mode.py")
text = path.read_text(encoding="utf-8")

old = '''def test_out_mode_returns_known_eating_out_candidates():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "out"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["mode"] == "out"
    assert payload["candidate_count"] == 2
    assert payload["known_eating_out_count"] == 2
    assert payload["empty_reason"] is None

    assert all(
        item["source"] == "restaurant"
        for item in payload["candidates"]
    )
'''

new = '''def test_out_mode_returns_known_candidates_plus_generic_filler():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "out"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["mode"] == "out"
    assert payload["candidate_count"] == 3
    assert payload["known_eating_out_count"] == 2
    assert payload["generic_eating_out_count"] == 1
    assert payload["empty_reason"] is None

    sources = {
        item["source"]
        for item in payload["candidates"]
    }

    assert "restaurant" in sources
    assert "generic_eating_out" in sources
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
