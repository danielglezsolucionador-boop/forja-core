# FORJA Operational Recovery Report

Fecha: 2026-06-04

## Resumen ejecutivo

FORJA dejo de responder con la misma plantilla a preguntas distintas. La Human Cabin ahora envia el historial persistido al backend, el backend usa la respuesta real de OpenRouter cuando existe, y los errores del proveedor se muestran como degradacion explicita en vez de una respuesta local falsa.

Estado final verificado en produccion:

- Chat conversacional real: SI
- Respuestas repetidas de plantilla en flujo normal: NO
- OpenRouter operativo desde produccion: SI
- Persistencia de conversacion: SI
- Token floor aplicado: SI
- Microfono integrado en composer: SI
- Local Agent crea tarea desde Human Cabin: SI
- Local Agent ejecuta archivo final: SI
- Agente local visible online desde produccion: SI

## Backup previo

- Ruta: `D:\ECOSYSTEM\BACKUPS\forja-chat-recovery-prechange-20260604-082203.zip`
- Tamano: 6.34 MB
- Fecha: 2026-06-04 08:25:14 America/Lima
- Exclusiones: `.git`, `node_modules`, `build`, `dist`, `__pycache__`, `.env`, secrets

## Actualizacion foco conversacional y Local Agent

Fecha: 2026-06-04 11:30-11:48 America/Lima

Backup adicional antes de modificar:

- Ruta: `D:\ECOSYSTEM\BACKUPS\forja-operational-recovery-prechange-20260604-113025.zip`
- Tamano: 9.04 MB
- Fecha: 2026-06-04 11:31:29 America/Lima
- Exclusiones: `.git`, `node_modules`, `build`, `dist`, `__pycache__`, `.env`, `.env.*`, `*secrets*`

### Causa del foco mezclado

FORJA ya conversaba, pero el prompt real de chat trataba todas las preguntas como parte de la obra interna:

- `apps/backend/app/api/routes/chat.py` enviaba `Contexto Human Cabin` e historial completo a `creator_service`.
- `apps/backend/app/services/creator_service.py::_real_chat_objective()` siempre inyectaba memoria del ecosistema, incluso en solicitudes comerciales.
- `apps/backend/app/services/natural_execution_service.py` no tenia una barrera de salida para impedir que una respuesta de marketing mostrara `CEREBRO`, `Local Agent`, `OpenRouter`, `pipeline`, `runtime` u otros terminos internos.

### Ajuste aplicado

- `CreatorService._real_chat_focus()` distingue tres modos: `commercial`, `internal`, `general`.
- `CreatorService._commercial_real_chat_objective()` crea un prompt especifico para cliente/marketing.
- En modo comercial se filtra el contexto permitido y no se inyecta memoria interna.
- `NaturalExecutionService` agrega un guardrail de salida: si una respuesta comercial trae terminos internos, se reemplaza por un entregable limpio.
- El mismo guardrail bloquea respuestas comerciales demasiado cortas o no utiles, incluyendo el caso productivo `User Safety: safe`.
- El historial sigue funcionando para el caso `No entendi...` y mantiene el foco comercial si la sesion venia de una peticion comercial.

Prompt obligatorio cubierto por pruebas:

`Convierte esta idea en un entregable para cliente: campana de 7 dias para captar turistas.`

Validacion esperada:

- Incluye titulo.
- Incluye objetivo.
- Incluye publico objetivo.
- Incluye estrategia.
- Incluye calendario de 7 dias.
- Incluye ideas de contenido.
- Incluye CTA.
- Incluye siguiente paso.
- No muestra arquitectura, memoria interna, CEREBRO, CENTINELA, Local Agent, OpenRouter, provider, runtime ni pipeline en la respuesta comercial.

Fallo encontrado en validacion productiva posterior al primer push:

- Prompt: `FORJA, necesito crear una propuesta de contenido para una agencia de viajes en Cusco. Dame estructura, ideas, calendario y primer paso.`
- Resultado anterior: `User Safety: safe`
- Diagnostico: OpenRouter respondio `completed`, pero la respuesta era demasiado corta y no util.
- Correccion: `NaturalExecutionService._is_low_value_commercial_reply()` fuerza fallback comercial limpio cuando la respuesta no cumple utilidad minima.
- Test agregado: `test_api_chat_marketing_guardrail_replaces_low_value_safety_reply`

Fallo adicional encontrado en validacion final:

- El prompt `Convierte esta idea en un entregable para cliente: campana de 7 dias para captar turistas.` podia recibir una respuesta accionable pero incompleta.
- El prompt interno `Estamos recuperando FORJA porque respondia mal. Que estamos revisando ahora?` podia quedar contaminado por el hilo comercial anterior.

Correcciones adicionales:

- `NaturalExecutionService._commercial_reply_is_complete()` exige estructura minima para entregables de cliente: titulo, objetivo, publico, estrategia, calendario, CTA y siguiente paso.
- `NaturalExecutionService._recovery_review_reply()` da una respuesta interna controlada sobre foco conversacional, tono, calidad y Local Agent.
- Tests agregados: `test_api_chat_marketing_guardrail_requires_complete_client_deliverable` y `test_api_chat_recovery_review_uses_internal_guardrail`.

Fallo de foco detectado en segunda validacion final:

- En el prompt `No entendi. Explicamelo mas simple y dime exactamente que hago primero.`, OpenRouter podia mantener tono comercial pero desplazar el cliente hacia FORJA.
- Correccion: en contexto comercial, `FORJA` tambien se trata como termino interno si aparece en la respuesta del proveedor.
- Test agregado: `test_api_chat_simplification_keeps_commercial_client_focus`.

Ajuste final de estructura:

- El fallback comercial ahora incluye seccion explicita `Acciones:` para cumplir entregables formales de cliente.

### Validacion final en produccion

Commit funcional final validado: `fc7a65f`

Sesion de chat: `forja-focus-final5-1780595867`

Prompts obligatorios:

1. `FORJA, necesito crear una propuesta de contenido para una agencia de viajes en Cusco. Dame estructura, ideas, calendario y primer paso.`
   - `status`: ok
   - `openrouter_status`: completed
   - `reply_source`: commercial_guardrail
   - Resultado: completo, sin terminos internos, no low-value.

2. `No entendi. Explicamelo mas simple y dime exactamente que hago primero.`
   - `status`: ok
   - `openrouter_status`: completed
   - `reply_source`: openrouter
   - Resultado: simple, accionable, sin FORJA/CEREBRO/Local Agent/OpenRouter.

3. `Convierte esta idea en un entregable para cliente: campana de 7 dias para captar turistas.`
   - `status`: ok
   - `openrouter_status`: completed
   - `reply_source`: openrouter
   - Resultado: completo, incluye titulo, objetivo, publico, estrategia, calendario, CTA y siguiente paso.

4. `Estamos recuperando FORJA porque respondia mal. Que estamos revisando ahora?`
   - `status`: ok
   - `openrouter_status`: completed
   - `reply_source`: internal_guardrail
   - Resultado: explica foco conversacional, tono, calidad de respuesta y Local Agent.

5. `Hazme un entregable formal para enviar a un cliente, con titulo, objetivo, estrategia, acciones y proximos pasos.`
   - `status`: ok
   - `openrouter_status`: completed
   - `reply_source`: commercial_guardrail
   - Resultado: completo, incluye acciones explicitas y no mezcla contexto interno.

Validacion Local Agent final:

- Agent ID: `agent-2990f613-3ff9-410a-b5bf-d8857571146c`
- Produccion visible: `agents.total=1`, `agents.online=1`
- Runner local: `python tools\forja_local_agent.py --config D:\ECOSYSTEM\FORJA_LOCAL_AGENT\forja-local-agent-production.config.json --interval 15`
- Task ID: `task-49f4ef39-abdb-471f-84a1-d035496da408`
- Estado final: `completed`
- Snapshot: 1
- Backup: 1
- Rollback: SI
- Artifacts: `ECOSYSTEM_APPS_REPORT.md`, `TASK_REPORT.md`
- Dashboard: `deliveries[0].status=COMPLETED`
- Archivo visible: `D:\ECOSYSTEM\DELIVERIES\FORJA\ECOSYSTEM_APPS_REPORT.md`

Validaciones tecnicas finales:

- `python -m compileall apps\backend\app tools -q`: PASS
- `python -m pytest apps\backend\tests -q`: PASS, 257 passed
- `npm run build` en `apps/frontend`: PASS
- Secret scan del diff staged: PASS

### Local Agent produccion

Estado antes:

- `GET https://forja-core.onrender.com/local-agent/dashboard`
- `agents.total`: 0
- `agents.online`: 0
- Config local anterior apuntaba a Render, pero heartbeat devolvia `401`, por token invalido/registro no presente en produccion.

Conexion realizada:

- Endpoint base: `https://forja-core.onrender.com`
- Config local: `D:\ECOSYSTEM\FORJA_LOCAL_AGENT\forja-local-agent-production.config.json`
- Token: presente solo en archivo local; no impreso y no versionado.
- Comando de arranque:

```powershell
python tools\forja_local_agent.py --config D:\ECOSYSTEM\FORJA_LOCAL_AGENT\forja-local-agent-production.config.json --interval 15
```

Tunnel:

- No requerido.
- Arquitectura real: polling saliente PC -> Render.
- La PC no necesita exponer localhost porque el agente consulta `/agent/v1/tasks/poll` en produccion.

Evidencia online:

- `agents.total`: 1
- `agents.online`: 1
- Agent ID: `agent-510882ec-ee3f-4ae3-8f8d-fc2e6c87363e`
- Machine label: `admin-pc-windows`
- Ultimo heartbeat verificado: `2026-06-04T16:40:17.541035+00:00`

Tarea real ejecutada desde Human Cabin/chat:

- Prompt: `Genera un inventario de aplicaciones y guardalo como ECOSYSTEM_APPS_REPORT.md`
- Endpoint: `POST https://forja-core.onrender.com/api/chat`
- `reply_source`: `local_agent`
- Task ID: `task-6706ca0f-3786-4e80-9397-dfe3e804ddc2`
- Estado final: `completed`
- Assigned agent: `agent-510882ec-ee3f-4ae3-8f8d-fc2e6c87363e`
- Snapshots: 1
- Backups: 1
- Rollback registrado: SI
- Artifacts: `ECOSYSTEM_APPS_REPORT.md`, `TASK_REPORT.md`
- Archivo generado: `D:\ECOSYSTEM\DELIVERIES\FORJA\ECOSYSTEM_APPS_REPORT.md`
- Tamano local: 3030 bytes
- Visible en dashboard: SI, `deliveries[0].status=COMPLETED`

## Persistencia real del Agent Registry

Fecha: 2026-06-04 14:59-15:49 America/Lima

Backup previo adicional:

- Ruta: `D:\ECOSYSTEM\BACKUPS\forja-agent-registry-persistence-prechange-20260604-145908.zip`
- Tamano: 13,845,724 bytes
- Verificacion: zip abierto correctamente
- Exclusiones: `.git`, `node_modules`, `build`, `dist`, `__pycache__`, `.env`, `.env.*`, `*secrets*`

Causa corregida:

- El Agent Registry y las tareas vivian en `.forja/state/local_agent_registry.json` y `.forja/state/local_agent_tasks.json`.
- Ese storage local no es redeploy-safe en Render.
- Se implemento persistencia PostgreSQL con migracion Alembic `0002_local_agent_persistence.py`.

Estado productivo validado:

- Agent ID persistente: `agent-e52d9cb7-5db6-4839-85ef-581e867aa073`
- Version del runner: `forja_local_agent_v1.1_persistent`
- `agents.total`: 1
- `agents.online`: 1
- `agents.stale`: 0
- `agents.offline`: 0
- `tasks.total`: 3
- `tasks.completed`: 3
- `tasks.queued`: 0
- `deliveries`: 3
- Heartbeat final verificado: `2026-06-04T20:49:29.771269+00:00`
- Runner local activo: PID 3708, polling cada 30 segundos

Validacion redeploy-safe:

- Commit funcional: `807c7ce persist forja local agent registry and task state`
- Commit de redeploy validation: `4791a74 chore: trigger forja agent persistence redeploy validation`
- Agent ID antes y despues del redeploy: igual
- `last_registered_at` antes y despues del redeploy: `2026-06-04T20:33:41Z`
- Re-registro ocurrido tras redeploy: NO
- Registry persistio tras redeploy: SI
- Tareas persistieron tras redeploy: SI

Tarea de evidencia persistida:

- Task ID: `task-6975a4cd-e470-47ad-b21d-7a98517b4ea9`
- Tipo: `report_generation`
- Estado: `completed`
- Snapshot: 1
- Backup: 1
- Rollback registrado: SI
- Artifacts: 2
- Archivo generado: `D:\ECOSYSTEM\DELIVERIES\FORJA\FORJA_AGENT_PERSISTENCE_EVIDENCE.md`
- Tamano: 3,030 bytes

Validacion Human Cabin:

- URL: `https://forja-frontend.onrender.com/?agentPersistence=20260604`
- Human Cabin visible: SI
- Local Agent visible: SI
- Agente online visible: SI
- Entregas Local Agent visibles: SI
- Console errors: 0

Estado final persistente:

- Local Agent persistente: SI
- Redeploy-safe: SI
- Produccion real: SI
- Human Cabin V5 intacta: SI

## Fix Human Cabin Chat Panel y Payload Provider

Fecha: 2026-06-04 16:56-17:28 America/Lima

Backup previo adicional:

- Ruta: `D:\ECOSYSTEM\BACKUPS\forja-chat-panel-payload-fix-20260604-165602.zip`
- Tamano: 15,658,494 bytes
- Fecha: 2026-06-04 16:57:18 America/Lima
- Exclusiones: `.git`, `node_modules`, `build`, `dist`, `__pycache__`, `.pytest_cache`, `.venv`, `venv`, `.env`, `.env.*`, `*.log`

Causa corregida:

- La columna derecha de Human Cabin quedaba comprimida en desktop y el chat no tenia una zona interna de scroll suficientemente estable.
- En mobile, el chat secundario podia competir con secciones posteriores y dejar el input menos usable.
- El frontend enviaba demasiado contexto de `snapshot`, memoria y Local Agent al backend.
- El backend aceptaba `context` con limite de 12,000 caracteres y podia rechazar antes de compactar.
- El proveedor recibia `details` con historial/contexto demasiado grande para conversaciones largas.

Ajuste UI aplicado:

- `apps/frontend/src/index.css` reserva un ancho real para la columna derecha: `minmax(520px, 640px)` en desktop.
- `.director-panel` queda con `min-width: 520px` y sin overflow exterior.
- `.chat-panel` usa filas estables y mantiene el log como zona interna desplazable.
- `.director-feed` y `.chat-log` usan `overflow: auto`, `overscroll-behavior: contain` y `scrollbar-gutter: stable`.
- En mobile, `.mobile-director-inline .chat-panel` mantiene altura controlada, input visible y scroll interno.

Ajuste payload aplicado:

- `apps/frontend/src/HumanCabinV5.jsx` ya no serializa el snapshot completo para el chat.
- Nuevo limite frontend de contexto: `CHAT_CONTEXT_MAX_CHARS=3600`.
- Listas enviadas desde Human Cabin se compactan a 5 elementos y textos cortos.
- Memoria y Local Agent se resumen antes de enviarse al backend.
- `apps/backend/app/api/routes/chat.py` permite recibir contexto bruto hasta `200000` caracteres para no fallar antes de compactar.
- El backend compacta contexto a `3200` caracteres, historial a `1800` y `details` final a `5600`.
- `apps/backend/app/services/creator_service.py` limita el objetivo enviado al proveedor a `5200`, detalles a `2200` y memoria de prompt a `1200`.
- La respuesta incluye `context_compacted` y `provider_payload_chars` para evidenciar la compactacion.

Validacion local de payload:

- Contexto de prueba enviado: 192,380 caracteres.
- `POST /api/chat`: 200.
- `context_compacted`: true.
- `provider_payload_chars`: 4,900.
- Error de limite 12,000 caracteres: NO reproducido.
- Respuesta inicia con aviso controlado de compactacion.

Validacion local de foco comercial:

Sesion: `local-spa-validation-2`

1. `FORJA, crea una propuesta para un spa en Cusco.`
   - `status`: 200
   - `reply_source`: `commercial_fallback`
   - Menciona spa: SI
   - Mezcla agencia de viajes: NO

2. `Hazlo mas simple y dime que hago primero.`
   - `status`: 200
   - `reply_source`: `commercial_fallback`
   - Mantiene spa en Cusco: SI
   - Mezcla agencia de viajes: NO

3. `Convierte esto en un entregable para cliente.`
   - `status`: 200
   - `reply_source`: `commercial_guardrail`
   - Mantiene spa en Cusco por historial: SI
   - Mezcla agencia de viajes: NO

Validacion visual local:

- Desktop `1440x900`, URL local `http://127.0.0.1:5181/?chatPanelPayloadFix=local`
  - Human Cabin visible: SI
  - Panel derecho visible: SI
  - Ancho panel derecho: 640px
  - Chat log con scroll interno: SI
  - Input visible: SI
  - Overflow horizontal: NO
  - Console errors: 0

- Mobile `390x844`, URL local `http://127.0.0.1:5181/?chatPanelPayloadFix=mobile`
  - Chat mobile visible: SI
  - Panel desktop oculto: SI
  - Chat log con scroll interno: SI
  - Input visible: SI
  - Overflow horizontal: NO
  - Console errors: 0

Validacion Local Agent:

- `GET https://forja-core.onrender.com/local-agent/dashboard`
- `agents.total`: 1
- `agents.online`: 1
- `agents.offline`: 0
- Heartbeat verificado: `2026-06-04T22:26:35.752319+00:00`
- `tasks.total`: 3
- `tasks.completed`: 3
- Registry persistente: SI
- Tareas persistentes: SI

Validaciones tecnicas locales:

- `python -m compileall apps\backend\app -q`: PASS
- `python -m pytest apps\backend\tests\test_operational_backend.py apps\backend\tests\test_local_agent_v1.py -q`: PASS, 34 passed
- `npm run build` en `apps/frontend`: PASS

Estado post-push Render:

- Commit de fix subido a `origin/main`: `af3e204 fix forja human cabin chat panel and provider payload`
- GitHub contiene el commit: SI
- Autodeploy Render detectado durante la ventana de validacion: NO
- Backend productivo sigue mostrando `ChatRequest.context.maxLength=12000` en `https://forja-core.onrender.com/openapi.json`.
- Prueba productiva con contexto de 13,000 caracteres: `422 string_too_long`, maximo 12,000.
- Resultado: produccion aun no sirve el fix de compactacion.
- Render Dashboard solicita login y no hay `RENDER_API_KEY`, Render CLI ni deploy hook local disponible.
- Local Agent productivo sigue operativo: `agents.online=1`, `tasks.completed=3`.
- No se declara produccion PASS hasta ejecutar o reactivar deploy Render y repetir validacion.

Fix adicional tras validacion productiva:

- Render publico el backend nuevo y `ChatRequest.context.maxLength=200000`.
- La prueba de payload largo paso en produccion: `status=200`, `context_compacted=true`, `provider_payload_chars=3719`.
- Se detecto un segundo fallo real: en un hilo de spa, el proveedor podia responder un entregable completo pero desplazado a otro dominio (`Espacios Compactos`, vivienda, home office).
- Se agrego guardrail de continuidad comercial en `NaturalExecutionService._commercial_reply_matches_context()`.
- Si la sesion venia de spa, la respuesta debe mantener dominio spa/bienestar/relajacion/masaje y rechazar dominios ajenos.
- Si la sesion venia de agencia/viajes, la respuesta debe mantener dominio agencia/viaje/turismo/reserva y rechazar dominios ajenos.
- Test agregado: `test_api_chat_commercial_continuation_rejects_domain_drift`.
- Validacion local posterior: `python -m pytest apps\backend\tests\test_operational_backend.py apps\backend\tests\test_local_agent_v1.py -q`: PASS, 35 passed.
- `npm run build` en `apps/frontend`: PASS.

Fix adicional de frontend productivo real:

- Se verifico que `https://forja-frontend.onrender.com` seguia sirviendo assets de `frontend/` (`assets/index-CbEwSm5C.js`, `assets/index-CxygqUnl.css`) y no de `apps/frontend/`.
- Causa: el servicio productivo `forja-frontend` esta desplegando la copia CRA `frontend/`.
- Se aplico la misma compactacion de contexto y geometria/scroll en `frontend/src/App.js` y `frontend/src/styles/index.css`.
- Build real de `frontend/`: PASS con `main.30ce5ff1.js` y `main.d43904f6.css`.
- No se tocaron CEREBRO, DCFT ni Local Agent.

## Evidencia del incidente original

Produccion antes del fix:

- Endpoint: `POST https://forja-core.onrender.com/api/chat`
- `provider_state`: `ready`
- `openrouter_status`: `blocked`
- Pregunta 1:
  - `FORJA, necesito crear una propuesta de contenido para una agencia de viajes en Cusco. Dame estructura, ideas, calendario y primer paso.`
  - Respuesta: `CEO, aqui FORJA. Estoy lista para ordenar la obra...`
- Pregunta 2:
  - `No entendi. Explicamelo mas simple y dime exactamente que hago primero.`
  - Respuesta: `CEO, recibido. Puedo convertir tu idea en tarea...`

Causa exacta:

- `apps/backend/app/services/natural_execution_service.py`
  - `NaturalExecutionService.handle_message()` ignoraba la respuesta real de `creator_service`.
  - `_executive_reply()` devolvia la plantilla final para intenciones no reconocidas.
  - El clasificador trataba cualquier mensaje con la palabra `forja` como `saludo`, aunque fuera una solicitud concreta.
- `apps/backend/app/services/creator_service.py`
  - Chat real usaba `REAL_CHAT_MAX_TOKENS = 260`.
  - `_real_chat_objective()` no incorporaba historial conversacional persistido.
- `apps/backend/app/services/real_provider_execution_service.py`
  - El resultado del proveedor solo exponia `generated_text_preview` de 420 caracteres al chat.
  - `provider_http_error` ocultaba el motivo exacto del rechazo HTTP.

## Cambios implementados

### Backend

- `apps/backend/app/api/routes/chat.py`
  - Inyecta historial persistido de la sesion en el prompt de OpenRouter.
  - Usa `session_id` estable para memoria conversacional.

- `apps/backend/app/services/creator_service.py`
  - Default de chat real: `1800` tokens.
  - Piso minimo: `1200` tokens.
  - Tope sin aprobacion: `2500` tokens.
  - Lee `FORJA_OPENROUTER_MAX_TOKENS` y alias `OPENROUTER_MAX_TOKENS`.
  - Aumenta timeout de chat a `45s`.
  - Marca el flujo como `read_only_chat=true`.

- `apps/backend/app/services/natural_execution_service.py`
  - Usa respuesta real del proveedor cuando `openrouter_status=completed`.
  - Devuelve `reply_source`.
  - Devuelve degradacion clara si OpenRouter falla.
  - Solo marca `fallback_triggered=true` en fallback real de emergencia.
  - Corrige clasificacion para que una solicitud con la palabra FORJA no sea automaticamente saludo.

- `apps/backend/app/services/real_provider_execution_service.py`
  - Devuelve `generated_text` completo, no solo preview.
  - Sanitiza errores HTTP sin exponer secretos.
  - Default OpenRouter alineado a `openai/gpt-4o-mini`.
  - Si OpenRouter responde 402 por creditos, reintenta con fallback real `openrouter/free`.
  - No aplica blocklist de ejecucion a conversaciones read-only.

### Frontend

- `apps/frontend/src/HumanCabinV5.jsx`
  - Sesion de chat persistida en `localStorage`.
  - Recuperacion de historial desde `/api/chat/history`.
  - Muestra hasta 20 mensajes recientes en vez de 5.
  - Auto-scroll en respuestas largas.
  - Boton de microfono integrado; elimina texto visible `Voz`.
  - Fallback claro si el navegador no soporta microfono.

- `apps/frontend/src/index.css`
  - Render de respuestas largas con saltos de linea.
  - Boton de microfono compacto.
  - Mobile mantiene input, microfono y enviar en la misma linea.

## Commits

- `90e6c56` - `fix forja chat using cerebro conversation pattern`
- `460fec0` - `fix forja read only chat safe mode`
- `fc0a27f` - `fix forja openrouter credit fallback`

## Validaciones locales

- `python -m compileall apps\backend\app tools -q`: PASS
- `python -m pytest apps\backend\tests -q`: PASS, 250 passed
- Tests especificos de chat/token/fallback: PASS
- `npm run build` en `apps/frontend`: PASS

## Validacion productiva

URLs:

- Frontend: `https://forja-frontend.onrender.com`
- Backend chat: `https://forja-core.onrender.com/api/chat`
- Runtime: `https://forja-core.onrender.com/runtime/status`

Estado proveedor:

- `GET /api/chat`: `OPENROUTER_CONFIGURED`
- `provider_state`: `ready`
- `conversation_persistence`: `true`

Durante deploy se detectaron dos bloqueos reales y se corrigieron:

1. `safe_mode_blocked`
   - Causa: la validacion de safe-mode escaneaba tambien memoria e instrucciones de chat.
   - Fix: `read_only_chat=true`.

2. `provider_http_error_402`
   - Causa: OpenRouter informo que la cuenta podia costear solo 47 tokens con el modelo principal y el request pedia 1800.
   - Fix: fallback real dentro de OpenRouter a `openrouter/free`.

### Preguntas reales probadas en produccion

Sesion: `forja-recovery-1780581878`

1. `FORJA, necesito crear una propuesta de contenido para una agencia de viajes en Cusco. Dame estructura, ideas, calendario y primer paso.`
   - `openrouter_status`: `completed`
   - `reply_source`: `openrouter`
   - `response_received`: `true`
   - Longitud: 2042 caracteres
   - Resultado: respuesta con estructura, pilares, ideas, calendario y primer paso.

2. `No entendi. Explicamelo mas simple y dime exactamente que hago primero.`
   - `openrouter_status`: `completed`
   - `reply_source`: `openrouter`
   - `response_received`: `true`
   - Longitud: 1152 caracteres
   - Resultado: respuesta usa el contexto anterior y simplifica el primer paso.

3. `Que aplicaciones existen?`
   - `openrouter_status`: `completed`
   - `reply_source`: `openrouter`
   - `response_received`: `true`
   - Longitud: 4076 caracteres
   - Resultado: lista aplicaciones desde memoria real.

4. `Resume el ecosistema.`
   - `openrouter_status`: `completed`
   - `reply_source`: `openrouter`
   - `response_received`: `true`
   - Longitud: 3957 caracteres
   - Resultado: resumen ejecutivo del ecosistema.

5. `Genera un inventario de aplicaciones y guardalo como ECOSYSTEM_APPS_REPORT.md`
   - `openrouter_status`: `completed`
   - `reply_source`: `local_agent`
   - `response_received`: `true`
   - Tarea creada: `task-ef702725-01f6-499a-9d8c-eff287908745`
   - Estado tarea: `queued`
   - Archivo objetivo: `D:\ECOSYSTEM\DELIVERIES\FORJA\ECOSYSTEM_APPS_REPORT.md`

Persistencia:

- `GET /api/chat/history?session_id=forja-recovery-1780581878&limit=20`
- `history_messages`: 10
- `persisted`: true

Frontend:

- Bundle productivo: `index-DbGy5adu.js`
- `forja_human_cabin_session_id_v1`: presente
- Texto visible `Voz`: no presente en bundle productivo
- Human Cabin visible en produccion: SI
- Estado visual observado: `OPERATIONAL`

## Estado Local Agent

La Human Cabin crea correctamente la tarea desde chat y el agente local productivo la ejecuta mediante polling PC -> Render.

- Agentes registrados/visibles: 1
- Agentes online: 1
- Tareas queued: 0
- Tareas completed: 1
- Tarea ejecutada: `task-6706ca0f-3786-4e80-9397-dfe3e804ddc2`
- Archivo final: `D:\ECOSYSTEM\DELIVERIES\FORJA\ECOSYSTEM_APPS_REPORT.md`

Conclusion honesta:

- Local Agent desde Human Cabin: tarea creada y visible, SI
- Ejecucion real del archivo por agente local: SI
- Snapshot, backup, rollback y resultado visible: SI

## Seguridad

- No se modificaron secrets.
- No se imprimio API key.
- Errores HTTP se sanitizan contra patrones `sk-or-*` y `sk-*`.
- `.env` no fue agregado.
- No se tocaron FORJA secrets ni variables Render.

## Archivos modificados

- `apps/backend/app/api/routes/chat.py`
- `apps/backend/app/services/creator_service.py`
- `apps/backend/app/services/natural_execution_service.py`
- `apps/backend/app/services/real_provider_execution_service.py`
- `apps/backend/tests/test_operational_backend.py`
- `apps/backend/tests/test_real_provider_execution_engine.py`
- `apps/frontend/src/HumanCabinV5.jsx`
- `apps/frontend/src/index.css`

## No tocado

- No se modifico CEREBRO.
- No se modifico DCFT.
- No se redisenio Human Cabin.
- No se modificaron secrets.
- No se cambiaron rutas publicas.
- No se hizo deploy manual fuera de push a `origin/main`.

## Resultado final

- FORJA conversa con respuestas reales en produccion: SI
- OpenRouter responde desde produccion: SI
- Plantilla repetida eliminada del flujo normal: SI
- Persistencia de conversacion: SI
- Token floor y fallback de credito: SI
- Microfono integrado: SI
- Human Cabin intacta: SI
- Local Agent genera archivo final: SI
