# FORJA Pre-Cloud Hardening

## Current Local Status

- Backend and frontend are local only.
- No remote repository is configured.
- No cloud provider is configured.
- External AI provider execution is disabled.
- Factory writes require governance approval and `allow_write=true`.

## Required Before Cloud

- Set `FORJA_APP_ENV` to the target environment.
- Set a strong `FORJA_JWT_SECRET`.
- Replace the bootstrap `FORJA_ADMIN_PASSWORD`.
- Configure `FORJA_CORS_ORIGINS` with exact dashboard origins.
- Configure `FORJA_DATABASE_URL` with PostgreSQL.
- Run Alembic migrations against the target database.
- Keep `FORJA_DB_AUTO_MIGRATE=false` unless an operational runbook explicitly allows startup migrations.

## Local PostgreSQL Migration

```powershell
cd C:\Users\admin\forja-knowledge-core
$env:FORJA_DATABASE_URL="postgresql+asyncpg://forja:forja@127.0.0.1:5432/forja_local"
$env:FORJA_DATABASE_SSL="false"
python -m alembic upgrade head
```

If PostgreSQL is not installed locally, `/health` reports database as `not_configured` or `unavailable` instead of pretending readiness.
