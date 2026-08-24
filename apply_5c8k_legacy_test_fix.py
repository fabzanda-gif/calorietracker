from pathlib import Path

targets = [
    Path("backend/tests/test_decision_feedback_test_isolation.py"),
    Path("backend/tests/test_optional_decision_learning_dependency.py"),
]

old = '''        assert response.json()["decision_preferences"] == {
            "preferred_mode": None,
            "preferred_lens": None,
            "preferred_source": None,
        }
'''

new = '''        prefs = response.json()["decision_preferences"]

        assert prefs["preferred_mode"] is None
        assert prefs["preferred_lens"] is None
        assert prefs["preferred_source"] is None
        assert prefs["mode_learning_source"] is None
        assert prefs["lens_learning_source"] is None
        assert prefs["source_learning_source"] is None
        assert prefs["outcome_evidence"] == {}
'''

changed = 0

for path in targets:
    text = path.read_text(encoding="utf-8")

    if old in text:
        path.write_text(
            text.replace(old, new, 1),
            encoding="utf-8",
        )
        print("Updated:", path)
        changed += 1
        continue

    if 'response.json()["decision_preferences"] == {' in text:
        raise SystemExit(
            f"Expected assertion shape changed in {path}; no automatic edit."
        )

    print("Already compatible:", path)

print("Changed files:", changed)
