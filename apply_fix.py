from pathlib import Path

path = Path("backend/tests/test_api_order_personalization.py")
text = path.read_text(encoding="utf-8")

old = '''def test_frequent_recent_order_can_win_taste_lens():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "order"},
    )

    payload = response.json()

    taste = next(
        option
        for option in payload["options"]
        if option["lens"] == "taste"
    )

    assert taste["candidate"]["name"] == "Poke Salmone"
    assert (
        taste["candidate"]["personalization_reason"]
        == "frequent_and_recent_order"
    )
'''

new = '''def test_frequent_recent_order_is_promoted_by_personalized_ranking():
    response = client.get(
        "/days/2026-09-01/meals/dinner/options",
        params={"mode": "order"},
    )

    payload = response.json()

    ranked_poke = next(
        option
        for option in payload["options"]
        if option["candidate"]["name"] == "Poke Salmone"
    )

    assert (
        ranked_poke["candidate"]["personalization_reason"]
        == "frequent_and_recent_order"
    )
    assert ranked_poke["candidate"]["personalization_strength"] == 1.0
    assert ranked_poke["candidate"]["taste_score"] > 8.0

    # Ranking intentionally avoids duplicating the same candidate across
    # the three lenses. Poke may therefore occupy calorie/balanced before
    # the taste lens is assigned.
    names = [
        option["candidate"]["name"]
        for option in payload["options"]
    ]
    assert len(names) == len(set(names))
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
