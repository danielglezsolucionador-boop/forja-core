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
