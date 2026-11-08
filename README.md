# SanoSync

SanoSync combines meal logging, calorie budgets, recipes and pantry management,
activity and weight history, training plans, and AI-assisted logging.

## Architecture

- `frontend/`: Next.js 15, React 19 and TypeScript. The current home is `HomeLite`.
- `/activities`: activity recap, calendar and logging; `/activities/programs`:
  running/strength programs and upcoming workouts. Weekly routine and special
  periods are managed from Profile. Legacy `/plan` links redirect to Activities.
- `backend/api/main.py`: complete FastAPI service, including AI and integrations.
- `backend/api/core_main.py`: optional smaller API for profile, onboarding, weight,
  progress and other frequently used endpoints. The frontend can fall back to the
  complete service for reads.
- `backend/services/`, `backend/repositories/`: business logic and Supabase access.
- `supabase/migrations/`: versioned database changes. Earlier SQL is also kept in
  `backend/sql/`; these historical scripts are not a fresh-install baseline.
- `app.py`: legacy Streamlit interface, retained separately from the web frontend.

## Local setup

Use Python 3.11 (matching CI) and Node.js 22. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pytest
cp .env.example .env.local
```

Fill in the backend Supabase URL, public key and server-only service role key in
`.env.local`. Set `CORS_ORIGINS=http://localhost:3000`. Use
`AI_RATE_LIMIT_BACKEND=memory` for local development without the quota migration;
production defaults to the shared Supabase store. Load the environment and start:

```bash
set -a
source .env.local
set +a
uvicorn backend.api.main:app --host 127.0.0.1 --port 8000 --reload
```

In another terminal:

```bash
cd frontend
cp .env.example .env.local
npm ci
npm run dev
```

Fill in the frontend public Supabase URL/key before starting. Open
http://localhost:3000. The complete API is sufficient locally. To run core too,
start `uvicorn backend.api.core_main:app --port 8001` with the same backend
environment and set frontend `NEXT_PUBLIC_CORE_API_BASE_URL=http://localhost:8001`.

Never put service-role, OAuth, Groq or VAPID secrets in `NEXT_PUBLIC_*` variables.
Frontend public variables are embedded at build time; rebuild after changing them.

## Database changes and deployment

For an existing installation, apply the pending versioned migrations before
updating **both** API services. In particular:

1. `20261108000909_fix_weight_move_atomic.sql` installs the authenticated,
   RLS-respecting RPC used when changing a weight measurement's date.
2. `20261108001828_shared_ai_rate_limits.sql` installs the server-only rolling
   AI quotas, shared across processes and restarts. Ensure
   `SUPABASE_SERVICE_ROLE_KEY` is configured on the complete API.

The default AI limits are 20 requests per rolling minute and 300 per rolling
24 hours, keyed by the **verified authenticated user**, including for demo
sessions. Token refresh does not reset quota. If shared quota storage is
unavailable, AI endpoints return 503 rather than bypassing the quota. The memory
backend is explicitly for local development/tests, not multi-worker production.

The weight RPC updates only weight and preserves steps, notes and daily context.
A missing or foreign source measurement returns 404. Briefings can still be shown
to demo users, but their generation never persists changes to the source account.
Exports page through user-owned histories and ingredient collections; OAuth and
push credentials are excluded. Operational AI quota counters are not exported.

Health probes: `/health/live` for process liveness, `/health/ready` for database
connectivity. The Dockerfile starts the core API on port 8080; the complete API
requires its own start command, e.g. `uvicorn backend.api.main:app --host 0.0.0.0
--port 8000`.

## Checks

```bash
python -m pytest -q
cd frontend
npm run lint
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
```

Builds require the public frontend environment variables. ESLint checks Next.js,
React hooks and TypeScript without interactive setup. Existing warnings remain
visible; errors fail the check. CI uses the committed npm lockfile and runs lint,
typechecking, production build and browser tests.

Browser tests exercise public pages, sign-in, the current navigation, meal
deletion, session restoration and logout through the real UI and Supabase SDK.
Network responses use deterministic fixtures, so no account credentials are
required and authenticated checks are not silently skipped. They complement the
backend tests; they do not verify a live OAuth provider or production database.
SQL regression harnesses in `backend/tests/sql/` use synthetic temporary data and
rollback; run them with the matching migration as described in their headers.

## Maintenance

The unreachable `HomeShell` and its CSS were removed; current Home behavior is
covered by browser tests. Keep new features in focused components/services.
The legacy Streamlit `app.py` remains a separate migration effort rather than a
second implementation to extend alongside the current web application.
