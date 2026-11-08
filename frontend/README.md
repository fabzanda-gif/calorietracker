# SanoSync Web

The current Next.js/React/TypeScript frontend includes authentication, onboarding,
Home (`HomeLite`), planning, AI logging, food management and progress views.

See the [project README](../README.md) for complete backend setup, migrations,
deployment order and security-related configuration.

```bash
cp .env.example .env.local
# Fill in the public Supabase URL and publishable key.
npm ci
npm run dev
```

Development: http://localhost:3000. The complete API defaults to
http://localhost:8000. `NEXT_PUBLIC_CORE_API_BASE_URL` optionally routes core reads
to a separate service, with fallback to the complete API.

Checks: `npm run lint`, `npm run typecheck`, `npm run build` and
`npm run test:e2e` (after `npx playwright install chromium`). Browser checks use
mocked network boundaries and always exercise authenticated UI flows in CI.
