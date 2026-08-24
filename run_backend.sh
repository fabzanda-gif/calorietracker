#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

eval "$(
python - <<'PY'
import re
import shlex
from pathlib import Path

path = Path(".streamlit/secrets.toml")

if not path.exists():
    raise SystemExit(
        "Errore: .streamlit/secrets.toml non trovato"
    )

text = path.read_text()

for name in ("SUPABASE_URL", "SUPABASE_KEY"):
    match = re.search(
        rf'^{name}\s*=\s*"([^"]+)"',
        text,
        re.M,
    )

    if not match:
        raise SystemExit(
            f"Errore: {name} non trovata"
        )

    print(
        f"export {name}={shlex.quote(match.group(1))}"
    )
PY
)"

echo "SanoSync backend"
echo "SUPABASE_URL: loaded"
echo "SUPABASE_KEY: loaded"
echo "Starting on http://localhost:8000"

exec env PYTHONPATH=. \
  uvicorn backend.api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --reload-dir backend
