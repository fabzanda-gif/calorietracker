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
