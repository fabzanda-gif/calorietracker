from pathlib import Path
import shutil


ROOT = Path("frontend")
PAYLOAD = Path("_5d4_payload/frontend")

if not ROOT.exists():
    raise SystemExit(
        "frontend/ non trovata. Esegui questo script dalla root del progetto."
    )

if not PAYLOAD.exists():
    raise SystemExit(
        "_5d4_payload/frontend non trovata."
    )

for source in PAYLOAD.rglob("*"):
    if source.is_dir():
        continue

    relative = source.relative_to(PAYLOAD)
    destination = ROOT / relative

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        source,
        destination,
    )

    print("Updated:", destination)

print()
print("5D.4 applicato.")
print("Ora esegui:")
print("  cd frontend")
print("  npm run typecheck")
