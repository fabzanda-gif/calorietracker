#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/.env.local" ]]; then
  set -a
  source "$ROOT/.env.local"
  set +a
fi

export SUPABASE_URL
export SUPABASE_KEY
export SUPABASE_ANON_KEY
export GROQ_API_KEY

echo "SanoSync development environment"
echo "--------------------------------"

# Secrets necessari al backend.
if [[ -z "${SUPABASE_URL:-}" ]]; then
  echo "ERRORE: SUPABASE_URL non è disponibile."
  echo "Controlla i GitHub Codespaces Secrets e riavvia il Codespace."
  exit 1
fi

if [[ -z "${SUPABASE_KEY:-}" ]]; then
  echo "ERRORE: SUPABASE_KEY non è disponibile."
  echo "Controlla i GitHub Codespaces Secrets e riavvia il Codespace."
  exit 1
fi

export SUPABASE_URL
export SUPABASE_KEY

echo "SUPABASE_URL: loaded"
echo "SUPABASE_KEY: loaded"

cleanup() {
  echo
  echo "Arresto SanoSync..."

  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi

  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi

  wait 2>/dev/null || true
}

trap cleanup INT TERM EXIT

echo
echo "Avvio backend su http://localhost:8000"

PYTHONPATH="$ROOT" \
uvicorn backend.api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload &
BACKEND_PID=$!

echo "Avvio frontend su http://localhost:3000"

(
  cd "$ROOT/frontend"
  npm run dev
) &
FRONTEND_PID=$!

echo
echo "--------------------------------"
echo "SanoSync avviato."
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000"
echo "--------------------------------"
echo
echo "Premi Ctrl+C per arrestare entrambi."

wait
