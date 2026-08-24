from pathlib import Path

path = Path("backend/tests/test_api_decision_feedback.py")
text = path.read_text(encoding="utf-8")

strict_name = "get_decision_selections_repository"
optional_name = "get_optional_decision_selections_repository"

changed = False

# 1. Fix import.
if strict_name in text and optional_name not in text:
    text = text.replace(
        strict_name,
        optional_name,
        1,
    )
    changed = True

# 2. Fix any remaining dependency override reference.
if f"app.dependency_overrides[{strict_name}]" in text:
    text = text.replace(
        f"app.dependency_overrides[{strict_name}]",
        f"app.dependency_overrides[{optional_name}]",
    )
    changed = True

# 3. Handle multiline override formatting if present.
if strict_name in text:
    remaining = [
        line
        for line in text.splitlines()
        if strict_name in line
    ]
    if remaining:
        raise SystemExit(
            "Strict dependency name still present after patch:\n"
            + "\n".join(remaining)
        )

if optional_name not in text:
    raise SystemExit(
        "Optional dependency was not found after patch."
    )

path.write_text(text, encoding="utf-8")

print("Updated:" if changed else "Already correct:", path)
print("Verified dependency:", optional_name)
