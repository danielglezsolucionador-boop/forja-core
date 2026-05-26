# FORJA Builder Core Stable

Snapshot final de Fase 4.7 para congelar Builder Core Foundation antes de revision CTO/CEO.

- Fecha: 2026-05-26
- Branch snapshot: `forja-builder-core-stable`
- Tag snapshot: `forja-builder-core-v1`
- Estado: Builder Core operacional inicial estable
- Alcance: Human Console + backend gobernado + workspaces seguros + archivos base controlados

## Que puede hacer FORJA

- Recibir ordenes humanas desde Human Console.
- Interpretar intencion con `IntentInterpretation` real.
- Generar `ProjectBlueprint` real desde la intencion.
- Evaluar riesgo `LOW`, `MEDIUM`, `HIGH`.
- Pedir approval para riesgo medio y bloquear alto riesgo sin autorizacion explicita.
- Crear workspace aislado en `.forja/workspaces/<request_id>/`.
- Generar archivos base controlados para `app`, `api`, `dashboard` y `module`.
- Completar workflows sin generacion compleja cuando el tipo todavia no esta soportado por File Generator.
- Registrar timeline, audit y outputs logicos sin exponer paths sensibles del sistema.
- Bloquear duplicados, ejecuciones paralelas, path traversal y escrituras fuera del workspace.

## Que no puede hacer todavia

- No ejecuta comandos externos en proyectos generados.
- No instala dependencias `npm` ni `pip` dentro de workspaces.
- No hace deploy automatico de proyectos generados.
- No activa IA externa ni providers externos.
- No modifica proyectos externos.
- No implementa Repair Engine.
- No avanza a Fase 5.

## Limites actuales

- Generacion compleja solo soportada para `app`, `api`, `dashboard` y `module`.
- `workflow` e `integration` pueden llegar a blueprint/workspace, pero no generan archivos complejos todavia.
- `repair` y `upgrade` son alto riesgo y quedan bloqueados salvo autorizacion explicita.
- Recovery operativo actual: el estado fallido queda recuperable por API/UI y la orden corregida puede ejecutarse con un nuevo request seguro.

## Governance actual

- Toda ejecucion pasa por `GovernedExecutionManager`.
- Estados soportados: `pending`, `interpreted`, `blueprint_ready`, `awaiting_approval`, `approved`, `generating`, `completed`, `blocked`, `failed`, `duplicate_blocked`.
- Bloqueos activos: bypass governance, duplicate execution, parallel execution, unsafe request id, path traversal, unsafe generation, overwrite accidental.
- Outputs se deduplican por `logical_path` para mantener visibilidad consistente.

## Approval model

- `LOW`: continua automaticamente para blueprint/docs/estructura basica.
- `MEDIUM`: requiere approval antes de crear workspace y generar archivos.
- `HIGH`: queda bloqueado antes de writes, con razon `high_risk_authorization_required`.
- Approval grant/reject se registra en audit y timeline.

## Workspace model

- Root logico: `.forja/workspaces/<request_id>/`.
- Archivos base: `README.md`, `blueprint.json`, `architecture.md`, `execution_report.md`.
- Directorios base: `frontend/`, `backend/`, `docs/`, `tests/`, `outputs/`, `audit/`.
- Seguridad: solo rutas relativas seguras, sin `../`, sin rutas absolutas externas, sin overwrite externo.

## Outputs

- Workspace base.
- README.
- Blueprint JSON.
- Architecture doc.
- Execution report.
- Generated directories.
- Generated files.
- Module/frontend/backend markers segun tipo.

## Audit

Eventos esperados:

- `execution_started`
- `approval_requested`
- `approval_granted`
- `approval_rejected`
- `workspace_creation_requested`
- `workspace_created`
- `generation_started`
- `files_generated`
- `generation_completed`
- `duplicate_execution_blocked`
- `execution_failed`
- `unsafe_path_blocked`
- `unsafe_generation_blocked`

## Rollback

1. Volver al tag estable:
   `git checkout forja-builder-core-v1`
2. Restaurar snapshot fuente sin secretos desde:
   `C:\Users\admin\forja-backups\forja-builder-core-stable-source-no-secrets-YYYYMMDD-HHMMSS.zip`
3. Si se necesita limpiar ejecuciones locales, revisar `.forja/state`, `.forja/workspaces` y `.forja/audit` sin borrar datos utiles.
4. No restaurar secretos desde backup: el backup se genera desde archivos versionados.

## Validaciones

Validaciones obligatorias de cierre:

- `python -m compileall apps/backend/app tools -q`
- `pytest -q`
- `npm run build` en `apps/frontend`
- `python tools/validate_forja.py`
- `git diff --check`
- Browser smoke desktop/tablet/mobile
- Console errors: `[]`
- Backend `/health`
- Backend `/runtime/status`

## URLs

- Human Console: `https://forja-frontend.onrender.com/#human-console-preview`
- Frontend: `https://forja-frontend.onrender.com/`
- Backend health: `https://forja-core.onrender.com/health`
- Backend runtime: `https://forja-core.onrender.com/runtime/status`

## Estado de cierre

Fase 4 queda lista para revision CTO/CEO despues de commit, push, tag, backup y verificacion publica.
No avanzar a Fase 5 sin siguiente prompt.
