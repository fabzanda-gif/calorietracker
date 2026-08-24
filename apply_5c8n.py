from pathlib import Path


API_ROOT = Path("backend/api")

old = "HTTP_422_UNPROCESSABLE_ENTITY"
new = "HTTP_422_UNPROCESSABLE_CONTENT"

changed = []

for path in API_ROOT.rglob("*.py"):
    text = path.read_text(encoding="utf-8")

    if old not in text:
        continue

    path.write_text(
        text.replace(old, new),
        encoding="utf-8",
    )
    changed.append(str(path))

if changed:
    print("Updated deprecated 422 constant in:")
    for item in changed:
        print(" -", item)
else:
    print("No deprecated 422 constants found in backend/api.")

# Defensive verification.
remaining = []

for path in API_ROOT.rglob("*.py"):
    text = path.read_text(encoding="utf-8")
    if old in text:
        remaining.append(str(path))

if remaining:
    raise SystemExit(
        "Deprecated constant still present in: "
        + ", ".join(remaining)
    )

print("422 status cleanup verified.")
