# FORJA Agent Registry Persistence Report

Fecha: 2026-06-04

## Objetivo

Eliminar la perdida del Agent Registry y de las tareas del Local Agent en cada deploy/restart de Render.

Restricciones cumplidas:

- No se toco CEREBRO.
- No se toco DCFT.
- No se redisenio FORJA.
- No se expusieron secrets.
- No se imprimio el token del agente.

## Backup previo

- Ruta: `D:\ECOSYSTEM\BACKUPS\forja-agent-registry-persistence-prechange-20260604-145908.zip`
- Tamano: 13,845,724 bytes
- Fecha: 2026-06-04 14:59 America/Lima
- Verificacion: zip abierto correctamente
- Exclusiones: `.git`, `node_modules`, `build`, `dist`, `__pycache__`, `.env`, `.env.*`, `*secrets*`

## Causa del problema

El Local Agent usaba storage JSON local:

- `.forja/state/local_agent_registry.json`
- `.forja/state/local_agent_tasks.json`

Ese almacenamiento depende del filesystem del proceso. En Render, el filesystem no es una fuente persistente confiable para estado operativo entre deploys/restarts. Por eso el registro del agente, tokens y tareas podian desaparecer despues de un deploy.

## Implementacion

Se agrego persistencia real en PostgreSQL cuando `FORJA_DATABASE_URL` esta disponible:

- Tabla `local_agent_agents`
- Tabla `local_agent_tasks`
- Migracion Alembic: `apps/backend/alembic/versions/0002_local_agent_persistence.py`
- Fallback local a JSON solo cuando la base de datos esta deshabilitada o no disponible en desarrollo.

Archivos principales modificados:

- `apps/backend/app/services/local_agent_service.py`
- `apps/backend/app/schemas/local_agent.py`
- `apps/backend/app/api/routes/local_agent.py`
- `apps/backend/app/core/config.py`
- `apps/backend/app/db/models.py`
- `apps/backend/alembic/versions/0002_local_agent_persistence.py`
- `render.yaml`
- `tools/forja_local_agent.py`
- `apps/backend/tests/test_local_agent_v1.py`
- `apps/frontend/src/HumanCabinV5.jsx`
- `apps/frontend/src/index.css`

## Seguridad

- Registro inicial permitido si no hay agentes en la base.
- Cuando ya existe al menos un agente y no hay token de registro configurado, se bloquean registros anonimos con `agent_registration_locked`.
- Soporte para `FORJA_LOCAL_AGENT_REGISTRATION_TOKEN` en produccion.
- `render.yaml` declara `FORJA_LOCAL_AGENT_REGISTRATION_TOKEN` como `sync: false`.
- El token operativo del agente queda solo en config local no versionada.

## Heartbeat y estado operativo

Se agrego calculo de estado por TTL:

- `online`: heartbeat menor o igual a 90 segundos.
- `stale`: heartbeat mayor a 90 segundos y menor o igual a 300 segundos.
- `offline`: heartbeat mayor a 300 segundos.

Dashboard productivo despues del fix:

- `agents.total`: 1
- `agents.online`: 1
- `agents.stale`: 0
- `agents.offline`: 0
- `status_message`: `Agente local online.`
- `last_heartbeat_at`: `2026-06-04T20:49:29.771269+00:00`

Runner local activo:

- PID: 3708
- Intervalo: 30 segundos
- Config: `D:\ECOSYSTEM\FORJA_LOCAL_AGENT\forja-local-agent-production.config.json`

## Re-registro automatico

El runner local ahora detecta:

- `agent_not_registered`
- `invalid_agent_token`
- `agent_revoked`

Si ocurre uno de esos casos, intenta re-registrarse mediante `/local-agent/agents` y guarda las nuevas credenciales en la config local.

Validacion post-redeploy:

- Agent ID antes: `agent-e52d9cb7-5db6-4839-85ef-581e867aa073`
- Agent ID despues: `agent-e52d9cb7-5db6-4839-85ef-581e867aa073`
- `last_registered_at` antes: `2026-06-04T20:33:41Z`
- `last_registered_at` despues: `2026-06-04T20:33:41Z`
- Re-registro ocurrido: NO
- Conclusion: el registry persistio y las credenciales siguieron validas despues del redeploy.

## Tarea productiva validada

Tarea de evidencia:

- Task ID: `task-6975a4cd-e470-47ad-b21d-7a98517b4ea9`
- Tipo: `report_generation`
- Riesgo: `high`
- Estado final: `completed`
- Assigned agent: `agent-e52d9cb7-5db6-4839-85ef-581e867aa073`
- Snapshot: 1
- Backup: 1
- Rollback registrado: SI
- Logs: 2
- Artifacts: 2
- Resultado: `completed`
- Completed at: `2026-06-04T20:37:27.190106+00:00`

Archivo generado:

- Ruta: `D:\ECOSYSTEM\DELIVERIES\FORJA\FORJA_AGENT_PERSISTENCE_EVIDENCE.md`
- Tamano: 3,030 bytes
- Visible en Human Cabin/dashboard: SI

Estado global de tareas tras limpieza:

- `tasks.total`: 3
- `tasks.completed`: 3
- `tasks.queued`: 0
- `tasks.running`: 0
- `deliveries`: 3

## Validacion de redeploy

Commit funcional:

- `807c7ce persist forja local agent registry and task state`

Commit usado para disparar redeploy de persistencia:

- `4791a74 chore: trigger forja agent persistence redeploy validation`

Ventana de verificacion post-push:

- `health`: ok durante la ventana.
- `agents.total`: 1 persistente.
- `tasks.total`: 3 persistente.
- `tasks.completed`: 3 persistente.
- `tasks.queued`: 0 persistente.

Despues de la ventana de redeploy, se ejecuto heartbeat con las mismas credenciales:

- Mismo `agent_id`: SI
- Mismo `last_registered_at`: SI
- Re-registro: NO
- Registry persistente: SI
- Tareas persistentes: SI

## Human Cabin

La Human Cabin V5 se mantuvo visualmente intacta. Solo se agrego un bloque compacto de estado Local Agent en la columna lateral.

Validacion UI produccion:

- URL: `https://forja-frontend.onrender.com/?agentPersistence=20260604`
- Human Cabin visible: SI
- Local Agent visible: SI
- Agente online visible: SI
- Entregas Local Agent visibles: SI
- Console errors: 0

## Validaciones tecnicas

- `python -m compileall apps\backend\app tools -q`: PASS
- `pytest apps\backend\tests\test_local_agent_v1.py apps\backend\tests\test_precloud_hardening.py -q`: PASS, 13 passed
- `pytest apps\backend\tests -q`: PASS, 259 passed
- `npm run build` en `apps/frontend`: PASS
- `python -m alembic upgrade head --sql`: PASS, incluye tablas `local_agent_agents` y `local_agent_tasks`
- Secret scan del diff staged: PASS
- Chat productivo `/api/chat`: PASS, `provider=openrouter`, `provider_state=ready`, `status=ok`
- Runtime snapshot con Local Agent: PASS

## Estado final

- Agent Registry persistente: SI
- Tareas persistentes: SI
- Heartbeat operativo: SI
- Re-registro automatico implementado: SI
- Redeploy-safe validado: SI
- Local Agent online visible en produccion: SI
- Human Cabin V5 intacta: SI
- CEREBRO tocado: NO
- DCFT tocado: NO

## Pendientes reales

- Configurar `FORJA_LOCAL_AGENT_REGISTRATION_TOKEN` en Render si se quiere permitir re-registro controlado despues de que ya existan agentes en la base.
- Mover el runner local a un servicio supervisado de Windows para autoarranque despues de reinicio de la PC.
