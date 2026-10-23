#!/usr/bin/env bash

cd "$(dirname "$0")"

eval "$(
python - <<'INNER_PY'
import os
import re
import shlex
from pathlib import Path

values = {}

secrets_path = Path(".streamlit/secrets.toml")
if secrets_path.exists():
    secrets_text = secrets_path.read_text()

    for name in (
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "GROQ_API_KEY",
    ):
        match = re.search(
            rf'^{name}\s*=\s*"([^"]+)"',
            secrets_text,
            re.M,
        )
        if match:
            values[name] = match.group(1)

env_path = Path(".env.local")
if env_path.exists():
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()

        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        name, value = line.split("=", 1)
        name = name.removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")

        if name in {
            "SUPABASE_URL",
            "SUPABASE_KEY",
            "GROQ_API_KEY",
        }:
            values[name] = value

for name in (
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "GROQ_API_KEY",
):
    value = os.getenv(name) or values.get(name)

    if value:
        print(f"export {name}={shlex.quote(value)}")
INNER_PY
)"

missing=0

for name in SUPABASE_URL SUPABASE_KEY GROQ_API_KEY; do
  if [ -z "${!name:-}" ]; then
    echo "Errore: $name non trovata" >&2
    missing=1
  fi
done

if [ "$missing" -ne 0 ]; then
  exit 1
fi

echo "SanoSync backend"
echo "SUPABASE_URL: loaded"
echo "SUPABASE_KEY: loaded"
echo "GROQ_API_KEY: loaded"
echo "Starting on http://localhost:8000"

exec env PYTHONPATH=. \
  uvicorn backend.api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --reload-dir backend
