from pathlib import Path

path = Path(
    "backend/tests/test_optional_decision_learning_dependency.py"
)
text = path.read_text(encoding="utf-8")

old = '''    assert response.json()["decision_preferences"] == {
        "preferred_mode": None,
        "preferred_lens": None,
        "preferred_source": None,
    }
'''

new = '''    prefs = response.json()["decision_preferences"]

    assert prefs["preferred_mode"] is None
    assert prefs["preferred_lens"] is None
    assert prefs["preferred_source"] is None
    assert prefs["mode_learning_source"] is None
    assert prefs["lens_learning_source"] is None
    assert prefs["source_learning_source"] is None
    assert prefs["outcome_evidence"] == {}
'''

if old in text:
    path.write_text(
        text.replace(old, new, 1),
        encoding="utf-8",
    )
    print("Updated:", path)
elif 'prefs = response.json()["decision_preferences"]' in text:
    print("Already updated:", path)
else:
    raise SystemExit(
        "Expected assertion not found. No changes made."
    )
