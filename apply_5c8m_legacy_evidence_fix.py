from pathlib import Path

targets = [
    Path("backend/tests/test_decision_feedback_test_isolation.py"),
    Path("backend/tests/test_optional_decision_learning_dependency.py"),
]

old = '    assert prefs["outcome_evidence"] == {}\n'
new = (
    '    assert prefs["outcome_evidence"] == {\n'
    '        "item_count": 0,\n'
    '        "observed_count": 0,\n'
    '    }\n'
)

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
    elif '"item_count": 0' in text and '"observed_count": 0' in text:
        print("Already compatible:", path)
    else:
        raise SystemExit(
            f"Expected outcome_evidence assertion not found in {path}"
        )

print("Changed files:", changed)
