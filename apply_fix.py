from pathlib import Path

path = Path("backend/tests/test_decision_ranking_feedback.py")
text = path.read_text(encoding="utf-8")

old = '''def test_preferred_lens_adds_bonus_only_to_that_lens():
    candidates = [
        candidate(
            "A",
            "delivery",
            500,
            30,
            7,
        ),
        candidate(
            "B",
            "takeaway",
            520,
            30,
            7,
        ),
    ]

    no_pref = service.rank(
        candidates=candidates,
        available_kcal=800,
        protein_remaining_g=50,
        mode="order",
    )

    with_pref = service.rank(
        candidates=candidates,
        available_kcal=800,
        protein_remaining_g=50,
        mode="order",
        preferred_lens="taste",
    )

    no_pref_taste = next(
        x for x in no_pref["options"]
        if x["lens"] == "taste"
    )
    with_pref_taste = next(
        x for x in with_pref["options"]
        if x["lens"] == "taste"
    )

    assert with_pref_taste["score"] > no_pref_taste["score"]
'''

new = '''def test_preferred_lens_adds_bonus_only_to_that_lens():
    candidates = [
        candidate(
            "A",
            "delivery",
            500,
            30,
            7,
        ),
        candidate(
            "B",
            "takeaway",
            520,
            30,
            7,
        ),
        candidate(
            "C",
            "delivery",
            540,
            30,
            7,
        ),
    ]

    no_pref = service.rank(
        candidates=candidates,
        available_kcal=800,
        protein_remaining_g=50,
        mode="order",
    )

    with_pref = service.rank(
        candidates=candidates,
        available_kcal=800,
        protein_remaining_g=50,
        mode="order",
        preferred_lens="taste",
    )

    no_pref_taste = next(
        x for x in no_pref["options"]
        if x["lens"] == "taste"
    )
    with_pref_taste = next(
        x for x in with_pref["options"]
        if x["lens"] == "taste"
    )

    assert with_pref_taste["score"] > no_pref_taste["score"]

    # The ranking must still keep all three lens choices distinct.
    names = [
        option["candidate"]["name"]
        for option in with_pref["options"]
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
