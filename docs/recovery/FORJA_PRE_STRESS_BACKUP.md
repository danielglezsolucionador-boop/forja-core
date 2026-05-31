# FORJA Pre-Stress Backup Snapshot

Snapshot creado antes de ejecutar pruebas destructivas/controladas sobre FORJA.

## Snapshot

- Fecha local: `2026-05-23`
- Timestamp backup: `20260523-060902`
- Source commit antes del documento: `1f266841919cf0f741ae853b048092723288e6b1`
- Branch recovery objetivo: `forja-pre-stress-stable`
- Tag recovery objetivo: `forja-pre-stress-v1`
- Frontend cloud: `https://forja-frontend.onrender.com`
- Backend cloud: `https://forja-core.onrender.com`
- Backend health: `https://forja-core.onrender.com/health`
- Runtime status: `https://forja-core.onrender.com/runtime/status`

## Backups

Destino: `C:\Users\admin\forja-backups`

- Source sin secrets: `C:\Users\admin\forja-backups\forja-pre-stress-source-no-secrets-20260523-060902.zip`
- Estado local: `C:\Users\admin\forja-backups\forja-pre-stress-state-20260523-060902.zip`
- PostgreSQL dump logico: `C:\Users\admin\forja-backups\forja-pre-stress-postgres-20260523-060902.dump`

El ZIP de source excluye:

- `.env`
- `.forja`
- `.venv`
- `node_modules`
- `dist`
- `.pytest_cache`
- `.git`

Validacion del ZIP source:

- Entradas: `248`
- Coincidencias prohibidas: `0`
- Tamano: `394054` bytes

Validacion del ZIP de estado:

- Entradas: `62`
- Tamano: `9890341` bytes

## PostgreSQL

- Cloud DB reportada por `/health`: `ok`
- Cloud DB reason: `connection_ok`
- Local `FORJA_DATABASE_URL`: configurada hacia `127.0.0.1/forja_local`
- Dump creado: si
- Formato: SQL logico con `CREATE TABLE` + `COPY`
- Tablas incluidas:
  - `ai_pipeline_requests`
  - `alembic_version`
  - `approval_requests`
  - `audit_events`
  - `factory_requests`
  - `workflow_runs`

Nota: el `pg_dump` local disponible es version `13.4` y el servidor local reporto `16.14`, por eso no se uso formato custom de `pg_dump`. Se creo dump logico compatible con `psql`.

## Render State

Backend:

- Service: `forja-backend`
- URL: `https://forja-core.onrender.com`
- Health: `ok`
- Environment: `staging`
- Production ready: `true`
- Database: `ok`
- Security warnings: none
- Runtime status: `active`
- Runtime loop: `not_started_by_design`
- Busy loop: `false`
- AI pipeline: `blocked_provider_disabled`

Frontend:

- Service: `forja-frontend`
- URL: `https://forja-frontend.onrender.com`
- HTTP status: `200`

## Variables Criticas Sin Secrets

No registrar valores secretos en git.

- `FORJA_APP_ENV=staging`
- `FORJA_DEBUG=false`
- `FORJA_DB_AUTO_MIGRATE=true`
- `FORJA_DATABASE_URL=configured_secret`
- `FORJA_JWT_SECRET=configured_secret`
- `FORJA_ADMIN_USERNAME=configured`
- `FORJA_ADMIN_PASSWORD=configured_secret`
- `FORJA_FRONTEND_ORIGIN=configured_cloud_frontend`
- `FORJA_CORS_ORIGINS=configured_cloud_origins`
- `PYTHON_VERSION=3.11.9`
- `VITE_FORJA_API_URL=https://forja-core.onrender.com`

## Rollback Rapido

Volver al codigo estable:

```powershell
cd C:\Users\admin\forja-knowledge-core
git checkout forja-pre-stress-stable
```

O volver al tag:

```powershell
cd C:\Users\admin\forja-knowledge-core
git checkout forja-pre-stress-v1
```

Restaurar source desde ZIP:

```powershell
Expand-Archive C:\Users\admin\forja-backups\forja-pre-stress-source-no-secrets-20260523-060902.zip C:\Users\admin\forja-restore\forja-source -Force
```

Restaurar estado local:

```powershell
cd C:\Users\admin\forja-knowledge-core
Rename-Item .forja ".forja.before-stress-restore" -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force .forja | Out-Null
Expand-Archive C:\Users\admin\forja-backups\forja-pre-stress-state-20260523-060902.zip .forja -Force
```

Restaurar PostgreSQL local desde dump logico:

```powershell
psql "$env:FORJA_DATABASE_URL" -f C:\Users\admin\forja-backups\forja-pre-stress-postgres-20260523-060902.dump
```

Si se necesita rollback cloud:

1. Redeploy Render backend desde `forja-pre-stress-v1`.
2. Redeploy Render frontend desde `forja-pre-stress-v1`.
3. Validar `/health`, `/runtime/status`, frontend `200` y DB `ok`.

## Validaciones Del Snapshot

- `git status` antes del documento: limpio sobre `main...origin/main`
- Frontend cloud: `200`
- Backend `/health`: `ok`
- Backend `/runtime/status`: `active`
- DB cloud: `ok`, `connection_ok`
- Source ZIP sin secrets: validado
- Estado local ZIP: creado
- PostgreSQL dump logico: creado

## Lo Que No Se Toco

- Codigo backend
- Codigo frontend
- UI
- Render config
- DB schema
- DB data, excepto lectura para dump
- Hermes
- DCFT
- Proveedores IA externos
