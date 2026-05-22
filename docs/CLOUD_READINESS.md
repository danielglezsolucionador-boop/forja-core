# FORJA Cloud Readiness

## Current Gate

FORJA is ready for a controlled cloud staging attempt only after these values are configured in the target platform:

- `FORJA_APP_ENV=staging` or `production`
- `FORJA_DEBUG=false`
- `FORJA_ADMIN_USERNAME`
- `FORJA_ADMIN_PASSWORD` with a generated secret
- `FORJA_JWT_SECRET` with a generated secret
- `FORJA_CORS_ORIGINS` with exact dashboard origins, never `*`
- `FORJA_FRONTEND_ORIGIN` matching the dashboard origin
- `FORJA_DATABASE_URL` pointing to managed PostgreSQL
- `FORJA_DATABASE_SSL=true`
- `FORJA_DB_AUTO_MIGRATE=false`

## Required Cloud Sequence

1. Create managed PostgreSQL.
2. Configure backend variables.
3. Run `python -m alembic upgrade head` once against the cloud database.
4. Start backend.
5. Confirm `/health` reports `status=ok`, `database.status=ok`, and `production_ready=true`.
6. Configure frontend API URL.
7. Build frontend.
8. Confirm dashboard reads the backend and shows `database OK`.

## Non-Goals

- Do not enable external AI providers during first cloud validation.
- Do not relax human-in-the-loop governance.
- Do not set wildcard CORS.
- Do not enable automatic writes outside approved factory flows.
