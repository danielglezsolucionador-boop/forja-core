# FORJA Recovery Snapshot

Estado congelado para `forja-stable-cloud-runtime` y `forja-cloud-stable-v1`.

## Snapshot

- Stable commit: `1339faa970bc150ef477f0eeb3d4bb2b63bb70db`
- Frontend URL: `https://forja-frontend.onrender.com`
- Backend URL: `https://forja-core.onrender.com`
- Backend service: `forja-backend`
- Frontend service: `forja-frontend`
- PostgreSQL service: `forja-postgres`
- Environment: `staging`
- Python: `3.11.9`
- App version: `0.1.0`

## Cloud Validation

Validated before this recovery document was created:

- `https://forja-frontend.onrender.com` -> `200`
- `https://forja-core.onrender.com/health` -> `status: ok`
- `https://forja-core.onrender.com/runtime/status` -> `status: active`
- Database status -> `ok`, `connection_ok`
- Runtime loop -> `not_started_by_design`
- Busy loop -> `false`
- Production ready -> `true`
- Security warnings -> empty

## Active Public Endpoints

- `GET /health`
- `GET /runtime/status`

## Active API Routes

- `POST /auth/login`
- `GET /auth/me`
- `POST /telemetry/events`
- `GET /telemetry/events`
- `POST /notifications`
- `GET /notifications`
- `POST /governance/approval-requests`
- `POST /governance/approval-requests/{request_id}/decision`
- `GET /governance/approval-requests`
- `GET /providers`
- `POST /ai/pipeline/requests`
- `GET /ai/pipeline/requests`
- `POST /factory/requests`
- `GET /factory/requests`
- `GET /factory/requests/{request_id}/plan`
- `POST /factory/requests/{request_id}/execute`
- `GET /factory/executions`
- `GET /ecosystem/integrations`
- `POST /workflows`
- `POST /workflows/{workflow_id}/advance`
- `GET /workflows`
- `GET /audit/events`
- `GET /validation/operational`

## Render Settings

Backend web service:

- Name: `forja-backend`
- Runtime: `python`
- Root Directory: `.`
- Plan: `starter`
- Build Command: `pip install --upgrade pip && pip install -r requirements.txt`
- Pre-Deploy Command: `PYTHONPATH=apps/backend python -m alembic upgrade head`
- Start Command: `bash apps/backend/start_render.sh`
- Health Check Path: `/health`

Frontend static service:

- Name: `forja-frontend`
- Runtime: `static`
- Root Directory: `apps/frontend`
- Build Command: `npm install && npm run build`
- Publish Directory: `dist`
- Frontend API variable: `VITE_FORJA_API_URL=https://forja-core.onrender.com`

Database:

- Name: `forja-postgres`
- Database: `forja`
- User: `forja`

## Required Variables

Backend required variables:

- `PYTHON_VERSION=3.11.9`
- `FORJA_APP_NAME=forja-backend`
- `FORJA_APP_VERSION=0.1.0`
- `FORJA_APP_ENV=staging`
- `FORJA_DEBUG=false`
- `FORJA_LOG_LEVEL=INFO`
- `FORJA_DATABASE_URL`
- `FORJA_DATABASE_SSL=true`
- `FORJA_DB_AUTO_MIGRATE=false`
- `FORJA_ADMIN_USERNAME=forja_admin`
- `FORJA_ADMIN_PASSWORD`
- `FORJA_JWT_SECRET`
- `FORJA_FRONTEND_ORIGIN=https://forja-frontend.onrender.com`
- `FORJA_CORS_ORIGINS=https://forja-frontend.onrender.com`

Frontend required variables:

- `VITE_FORJA_API_URL=https://forja-core.onrender.com`

Never commit `.env`, `.forja`, `.venv`, secrets, or database URLs.

## Startup Structure

Render starts the backend with:

```bash
bash apps/backend/start_render.sh
```

The script:

- Enters `apps/backend`
- Sets `PYTHONPATH=.`
- Sets `PYTHONUNBUFFERED=1`
- Runs an import precheck for `app.main`
- Executes `render_bootstrap.py`

The backend app is declared in:

```text
apps/backend/app/main.py
```

The backend imports internal modules with `from app...`, so Render must preserve the startup script or equivalent `PYTHONPATH` behavior.

## Runtime Structure

Runtime summary at snapshot:

- Backend: `active`
- Auth: `active`
- Telemetry: `active`
- Notifications: `local_queue`
- Factory: `hitl_required`
- Runtime: `local_status_only`
- AI pipeline: `provider_disabled`
- Database: `ok`
- Human in the loop: `true`
- Zero write policy: `true`
- External AI provider execution: disabled by design

## Critical Commits

- `1339faa` improve forja frontend controls and pwa branding
- `7b53ec1` ignore local forja state artifacts
- `63f3c90` align forja frontend render build command
- `8535d74` build enterprise forja frontend dashboard
- `1bdc3c3` add psycopg2 for render migrations
- `a8391bd` add render bootstrap crash diagnostics
- `fcdee53` instrument render startup diagnostics
- `6e6d1da` officialize forja render startup

## Quick Rollback

To return local code to this stable snapshot:

```bash
git fetch origin --tags
git checkout forja-cloud-stable-v1
```

To create a recovery branch from the stable tag:

```bash
git fetch origin --tags
git checkout -b recovery/forja-cloud-stable-v1 forja-cloud-stable-v1
```

To reset `main` back to the stable tag only after explicit human approval:

```bash
git fetch origin --tags
git checkout main
git reset --hard forja-cloud-stable-v1
git push --force-with-lease origin main
```

## If Frontend Breaks

1. Do not change backend.
2. In Render, confirm frontend service uses:
   - Root Directory: `apps/frontend`
   - Build Command: `npm install && npm run build`
   - Publish Directory: `dist`
   - `VITE_FORJA_API_URL=https://forja-core.onrender.com`
3. Locally verify:

```bash
cd apps/frontend
npm install
npm run build
```

4. Roll frontend code back to the stable tag:

```bash
git checkout forja-cloud-stable-v1 -- apps/frontend
```

5. Commit and push the frontend rollback.

## If Backend Breaks

1. Do not change frontend unless CORS URL changed.
2. Verify Render backend service still uses:
   - Root Directory: `.`
   - Build Command: `pip install --upgrade pip && pip install -r requirements.txt`
   - Pre-Deploy Command: `PYTHONPATH=apps/backend python -m alembic upgrade head`
   - Start Command: `bash apps/backend/start_render.sh`
   - Health Check Path: `/health`
3. Verify required variables are present and not wildcarded.
4. Locally verify:

```bash
python -m compileall apps/backend/app -q
pytest -q
python tools/validate_forja.py
```

5. Roll backend code back to the stable tag:

```bash
git checkout forja-cloud-stable-v1 -- requirements.txt alembic.ini apps/backend tools packages
```

6. Commit and push the backend rollback.

## Post-Rollback Checks

Run:

```bash
curl https://forja-core.onrender.com/health
curl https://forja-core.onrender.com/runtime/status
```

Expected:

- `/health`: `status` is `ok`
- `/runtime/status`: `status` is `active`
- Database: `status` is `ok`, `reason` is `connection_ok`
- Frontend opens at `https://forja-frontend.onrender.com`
