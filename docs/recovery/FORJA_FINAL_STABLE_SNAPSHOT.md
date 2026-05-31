# FORJA Final Stable Snapshot

Snapshot final creado despues de hard break testing, correcciones de idempotencia, limpieza de lifecycle asyncpg y validacion cloud.

## Estado Final

- Fecha local: `2026-05-23`
- Timestamp backup: `20260523-074700`
- Code commit estable antes del documento: `c58669b resolve pre snapshot execution idempotency`
- Branch final: `forja-final-stable-cloud`
- Tag final: `forja-final-stable-v1`
- Frontend cloud: `https://forja-frontend.onrender.com`
- Backend cloud: `https://forja-core.onrender.com`
- Health: `https://forja-core.onrender.com/health`
- Runtime status: `https://forja-core.onrender.com/runtime/status`

## Backups Finales

Destino: `C:\Users\admin\forja-backups`

- Source sin secrets: `C:\Users\admin\forja-backups\forja-final-stable-source-no-secrets-20260523-074700.zip`
- Estado local: `C:\Users\admin\forja-backups\forja-final-stable-state-20260523-074700.zip`
- PostgreSQL dump: `C:\Users\admin\forja-backups\forja-final-stable-postgres-20260523-074700.dump`

Validacion de backups:

- Source ZIP: `167` entradas, `0` coincidencias prohibidas.
- Estado local ZIP: `1161` entradas. Los logs transitorios `*.log` se excluyeron porque uno estaba bloqueado por un proceso local de frontend.
- PostgreSQL dump: creado como dump logico de datos con `asyncpg` porque `pg_dump.exe` no estaba disponible en PATH ni en rutas PostgreSQL conocidas. La recuperacion de schema debe hacerse con Alembic y luego cargar los datos.

El ZIP de source debe excluir:

- `.env`
- `.forja`
- `.venv`
- `node_modules`
- `dist`
- `.pytest_cache`
- `.git`

## URLs Y Servicios

Backend:

- Service: `forja-core`
- Public URL: `https://forja-core.onrender.com`
- Health status: `ok`
- Runtime status: `active`
- Database status: `ok`
- Production ready: `true`
- Busy loop: `false`
- Runtime loop: `not_started_by_design`

Frontend:

- Service: `forja-frontend`
- Public URL: `https://forja-frontend.onrender.com`
- HTTP status: `200`
- Browser smoke: Creator Console visible, no console errors.

## Variables Criticas Sin Secrets

No registrar valores secretos en git.

Backend:

- `PYTHON_VERSION=3.11.9`
- `FORJA_APP_NAME=forja-backend`
- `FORJA_APP_VERSION=0.1.0`
- `FORJA_APP_ENV=staging`
- `FORJA_DEBUG=false`
- `FORJA_LOG_LEVEL=INFO`
- `FORJA_DATABASE_URL=configured_secret`
- `FORJA_DATABASE_SSL=true`
- `FORJA_DB_AUTO_MIGRATE=false` o pre-deploy migrations controladas
- `FORJA_ADMIN_USERNAME=forja_admin`
- `FORJA_ADMIN_PASSWORD=configured_secret`
- `FORJA_JWT_SECRET=configured_secret`
- `FORJA_FRONTEND_ORIGIN=https://forja-frontend.onrender.com`
- `FORJA_CORS_ORIGINS=https://forja-frontend.onrender.com`

Frontend:

- `VITE_FORJA_API_URL=https://forja-core.onrender.com`

## Pruebas Superadas

Validaciones locales:

- `python -m compileall apps\backend\app tools -q`: OK
- `pytest -q`: `20 passed`
- `python tools\validate_forja.py`: OK
- `npm run build`: OK
- `git diff --check`: OK
- `python -m alembic current`: `0001_precloud_foundation (head)`

Validaciones cloud:

- Frontend cloud: `200`
- Backend `/health`: `ok`
- Backend DB: `ok`
- Backend `/runtime/status`: `active`
- Creator Console: `controlled_execution_engine`
- Governance: provider disabled by governance
- Capability runtime: `external_api_calls=0`
- Zero-write policy: `true`
- Human-in-the-loop: `true`
- Browser smoke: OK, sin errores de consola

Funcionalidad estabilizada:

- Creator Console
- Execution Engine
- Output Manager
- Capability Request system
- Capability Consumption safe mode
- Audit
- Governance
- Mobile layout

## Correcciones Incluidas Antes Del Freeze

- Idempotencia del Execution Engine: una request `completed` no genera outputs duplicados.
- Bloqueo de ejecucion paralela: una request `executing` no arranca ejecucion duplicada.
- Audit de reintento: `creator.duplicate_execution_blocked`.
- Timeline de reintento: `execution.duplicate_blocked`.
- Lifecycle asyncpg local/test: `NullPool` en entorno local para evitar warning de conexiones persistentes entre loops de test.
- Audit concurrente: timestamps dentro de lock.
- Frontend: timeouts de request y loading states seguros.
- Mobile: badges largos sin overflow.

## Riesgos Aceptados

- Creator/output history es metadata-only y depende del almacenamiento de estado de FORJA; persistencia historica de largo plazo debe tratarse como hardening futuro separado.
- Execution Engine sigue en modo metadata-only; no crea codigo real, no despliega, no llama proveedores y no escribe artefactos productivos.
- Render free tier puede tener cold starts y latencia inicial.
- Integraciones externas permanecen bloqueadas hasta aprobacion explicita por CEO/Cerebro y nueva capa superior.

## Rollback

Volver localmente al snapshot final:

```powershell
cd C:\Users\admin\forja-knowledge-core
git fetch origin --tags
git checkout forja-final-stable-v1
```

Crear rama de recovery:

```powershell
cd C:\Users\admin\forja-knowledge-core
git fetch origin --tags
git checkout -b recovery/forja-final-stable-v1 forja-final-stable-v1
```

Restaurar source desde ZIP:

```powershell
Expand-Archive C:\Users\admin\forja-backups\forja-final-stable-source-no-secrets-20260523-074700.zip C:\Users\admin\forja-restore\forja-final-source -Force
```

Restaurar estado local:

```powershell
cd C:\Users\admin\forja-knowledge-core
Rename-Item .forja ".forja.before-final-restore" -ErrorAction SilentlyContinue
Expand-Archive C:\Users\admin\forja-backups\forja-final-stable-state-20260523-074700.zip C:\Users\admin\forja-knowledge-core -Force
```

Restaurar PostgreSQL local desde dump logico:

```powershell
psql "$env:FORJA_DATABASE_URL" -f C:\Users\admin\forja-backups\forja-final-stable-postgres-20260523-074700.dump
```

Rollback cloud:

1. Redeploy backend en Render desde `forja-final-stable-v1`.
2. Redeploy frontend en Render desde `forja-final-stable-v1`.
3. Validar `https://forja-core.onrender.com/health`.
4. Validar `https://forja-core.onrender.com/runtime/status`.
5. Abrir `https://forja-frontend.onrender.com`.

Resetear `main` al snapshot solo con aprobacion explicita:

```powershell
git checkout main
git reset --hard forja-final-stable-v1
git push --force-with-lease origin main
```

## Restricciones De Freeze

Despues de este snapshot, FORJA CORE queda congelado.

No tocar sin autorizacion CTO/CEO:

- `apps/backend/app/main.py`
- `apps/backend/start_render.sh`
- `apps/backend/app/core/config.py`
- `apps/backend/app/db/session.py`
- `apps/backend/app/services/creator_service.py`
- Render backend service config
- Render frontend static site config
- DB config y migrations
- Governance gates
- Zero-write policy
- Human approval flow
- Capability safe-mode boundaries

## Que Se Puede Extender

Nuevas funciones deben hacerse como extensiones o capas superiores:

- Nueva consola visual encima del core estable.
- Nuevos paneles frontend que consuman endpoints existentes.
- Nuevos providers solo detras de Capability Request, aprobacion humana y safe wrapper.
- Nuevos reportes o dashboards de lectura.
- Nuevos documentos/runbooks.
- Nuevos adapters aislados que no cambien semantica del core.

## Cierre Oficial

FORJA queda congelado como `forja-final-stable-v1`.

Estado recomendado CTO: estable final, listo para snapshot y recovery controlado.
