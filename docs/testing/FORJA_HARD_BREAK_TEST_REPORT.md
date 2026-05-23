# FORJA Hard Break Test Report

Fecha: 2026-05-23
Repositorio: `forja-core`
Frontend cloud: `https://forja-frontend.onrender.com`
Backend cloud: `https://forja-core.onrender.com`
Snapshot previo: branch `forja-pre-stress-stable`, tag `forja-pre-stress-v1`

## Resultado CTO

FORJA resistio de forma parcial.

El core operativo aguanto pruebas concurrentes, payloads invalidos, controles de governance, approvals, execution metadata-only, outputs, capabilities safe mode, audit y cloud smoke sin activar IA externa ni llamadas reales a providers. Se corrigieron fallos pequenos detectados durante la prueba.

No recomiendo snapshot final todavia hasta decidir el comportamiento idempotente de ejecuciones repetidas/concurrentes sobre la misma solicitud.

## Alcance Ejecutado

- Frontend stress: clicks rapidos, botones, loading states, error states, mobile 390x844, consola y overflow.
- Backend stress: `/health`, `/runtime/status`, `/creator/console`, requests concurrentes, payloads invalidos y payloads grandes.
- Creator Console: sender `user`, `cerebro`, `seo`, `system`, request vacia, request enorme, request duplicada y routing de respuesta.
- Governance: ejecucion sin approval, approval inexistente, provider disabled, intento no metadata-only y capability no autorizada.
- Execution Engine: metadata-only, ejecucion sin capability, capability rechazada, ejecucion concurrente y timeline.
- Output Manager: output generado, output bloqueado, listing, metadata download, missing output y asociacion de output.
- Capability Requests: OCR, coding, imagen, voz, video, mas contexto, menor costo, approve, reject y consumo safe mode.
- Audit: generacion de eventos, parse JSONL, orden cronologico y validacion concurrente posterior al fix.
- DB/storage: migracion actual, inserts concurrentes, lecturas concurrentes y estado cloud DB.
- Cloud: frontend Render 200, backend `/health` OK, backend `/runtime/status` OK, CORS operativo y mobile smoke.
- Security: secretos, `.env`, `.forja`, `.venv`, CORS, JWT default, admin password default y exposicion frontend.

## Evidencia

- Stress local HTTP: `.forja/state/forja-hard-break-http-results.json`
- Captura mobile cloud final: `.forja/state/forja-hard-break-cloud-mobile-final-badge-fixed2.png`
- Capturas intermedias: `.forja/state/forja-hard-break*.png`
- Frontend bundle cloud confirmado: `index-CVp62fR0.js`, `index-BveXYhqG.css`
- Browser smoke cloud final: submit vuelve a estado normal, sin `Working...` colgado, sin errores de consola.
- Backend cloud: frontend 200, health `ok`, database `ok`, runtime `active`, busy loop `false`.

## Stress Backend

- `/health`: 120 requests, 24 workers, status 200, p95 4461 ms.
- `/runtime/status`: 120 requests, 24 workers, status 200, p95 4627 ms.
- `/creator/console`: 40 requests, 12 workers, status 200, p95 3493 ms.
- Payloads invalidos: respondieron 422 sin crash.
- Approval inexistente: respondio 404 sin crash.
- Provider disabled: bloqueo aplicado sin llamada externa.

## Fallos Encontrados

1. Audit chronology bajo concurrencia: el timestamp se creaba antes del lock y podia escribirse fuera de orden.
2. `.forja/outputs/.gitkeep` estaba trackeado, dejando una ruta de estado local dentro de git.
3. Frontend podia quedar con boton en loading bajo clicks rapidos si una request quedaba colgada.
4. Badge mobile `provider disabled by governance` desbordaba horizontalmente en 390x844.
5. Ejecuciones metadata-only repetidas/concurrentes sobre una misma solicitud generan outputs adicionales. No corrompe estado, pero requiere decision de idempotencia.
6. `pytest` mantiene un warning existente de `asyncpg Connection._cancel was never awaited`.
7. El primer harness con `TestClient` compartido se colgo bajo concurrencia extrema; el harness HTTP real no reprodujo crash de FORJA.

## Correcciones Hechas

- `apps/backend/app/core/audit.py`: creacion de evento y timestamp movida dentro de `_audit_lock`.
- `.gitignore`: `.forja/` queda ignorado completo.
- `.forja/outputs/.gitkeep`: eliminado del tracking.
- `apps/frontend/src/lib/api.ts`: timeout de 15 s con `AbortController`.
- `apps/frontend/src/App.tsx`: loading visible como `Working...` y labels de badges con guiones bajos humanizados.
- `apps/frontend/src/index.css`: wrapping y layout de badges mobile corregido para 390x844.

## Validacion Posterior A Correcciones

- `python -m compileall apps\backend\app tools -q`: OK.
- `pytest -q`: 18 passed, 1 warning existente de asyncpg.
- `python tools\validate_forja.py`: OK.
- `npm run build`: OK.
- `git diff --check`: OK.
- `python -m alembic current`: `0001_precloud_foundation (head)`.
- Audit concurrente posterior al fix: 320 eventos, orden cronologico true, corrupt 0.
- Cloud `/health`: OK, DB OK.
- Cloud `/runtime/status`: active, busy loop false.
- Browser smoke cloud: OK, sin errores de consola.
- Mobile smoke 390x844: OK, sin badge cortado en captura final.

## Seguridad

- `.env`, `.forja` y `.venv` no quedan trackeados.
- `.env`, `.forja/`, `.venv/` confirmados por `git check-ignore`.
- Escaneo `rg` encontro solo falsos positivos en tests, package-lock y referencias de codigo.
- Runtime cloud reporta `production_ready=true` por `/health`.
- Capability runtime cloud reporta `external_api_calls=0` y `external_api_calls_enabled=false`.

## Fallos No Corregidos

- Idempotencia de execution engine: decidir si ejecutar dos veces la misma request debe crear nuevo output, devolver el output existente, o bloquear por estado terminal. Esta decision toca semantica del Execution Engine y debe aprobarla CTO/CEO.
- Warning asyncpg en tests: requiere revisar ciclo de vida de conexion/cancelacion. No se corrigio porque puede tocar DB/session lifecycle.

## Riesgos

- Riesgo medio: sin regla de idempotencia, un usuario puede generar outputs duplicados metadata-only para una misma solicitud.
- Riesgo bajo: warning asyncpg no rompe tests ni cloud, pero debe limpiarse antes de endurecimiento final.
- Riesgo bajo: cold start de Render free tier puede elevar latencia inicial; no se detecto caida.

## Commits De Correccion

- `ee8bdbb` fix hard break stress findings
- `e309ac2` fix mobile status badge overflow
- `ed95656` harden mobile status badge wrapping
- `1a21e8e` fix mobile status badge wrapping override
- `bbdda4d` harden status badge labels
- `95dad2f` fix mobile status badge layout
- `bad1a4b` compact mobile status badges

## Rollback

Rollback rapido al estado previo al stress:

```powershell
git fetch origin --tags
git checkout forja-pre-stress-v1
```

Rollback de main a snapshot estable:

```powershell
git checkout main
git reset --hard forja-pre-stress-v1
git push origin main --force-with-lease
```

Usar force push solo con aprobacion explicita del CEO/CTO.

## Decision

FORJA no colapso bajo hard break testing. Respuesta CTO recomendada: parcial, aprobar correcciones pequenas ya aplicadas, abrir decision formal para idempotencia del Execution Engine antes de snapshot final.
