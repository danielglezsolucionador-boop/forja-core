from __future__ import annotations

from app.core.audit import read_audit_events, utc_now
from app.services.creator_service import creator_service
from app.services.ecosystem_memory_service import ecosystem_memory_service
from app.services.local_agent_service import local_agent_service


class HumanCabinSnapshotService:
    def snapshot(self) -> dict:
        memory = ecosystem_memory_service.snapshot()
        commands = creator_service.list_commands(limit=30)
        outputs = creator_service.list_outputs(limit=30)
        audit_events = read_audit_events(40)
        local_agent = self._compact_local_agent_dashboard(local_agent_service.dashboard())

        active_apps = memory.get("active_apps") or memory.get("registered_apps", [])
        construction_queue = self._construction_queue(memory)
        blockers = self._blockers(memory)
        approvals = [*self._approvals(commands), *self._local_agent_approvals(local_agent)]
        deliveries = [*self._deliveries(outputs, memory), *self._local_agent_deliveries(local_agent)]
        activity = [*self._activity(commands, audit_events), *self._local_agent_activity(local_agent)]
        flow = self._flow(memory, construction_queue, approvals, blockers, deliveries)

        return {
            "source": "ecosystem_memory_runtime_snapshot",
            "generated_at": utc_now(),
            "memory": {
                "connected": memory.get("connected", False),
                "primary_source": memory.get("primary_source", {}).get("path"),
                "additional_sources": [source.get("path") for source in memory.get("additional_sources", []) if source.get("exists")],
                "registered_apps": memory.get("registered_apps", []),
                "active_apps": active_apps,
                "apps_missing_from_primary_memory": memory.get("apps_missing_from_primary_memory", []),
            },
            "localAgent": local_agent,
            "metrics": self._metrics(active_apps, construction_queue, approvals, blockers, deliveries, activity),
            "services": self._services(memory),
            "constructionQueue": construction_queue,
            "flow": flow,
            "approvals": approvals,
            "blockers": blockers,
            "activity": activity,
            "deliveries": deliveries,
        }

    def _metrics(
        self,
        active_apps: list[str],
        construction_queue: list[dict],
        approvals: list[dict],
        blockers: list[dict],
        deliveries: list[dict],
        activity: list[dict],
    ) -> list[dict]:
        return [
            {
                "label": "Apps en construccion",
                "value": str(len(active_apps)),
                "detail": f"{len(active_apps)} apps activas desde memoria real.",
                "status": "OPERATIONAL" if active_apps else "UNKNOWN",
            },
            {
                "label": "Tareas activas",
                "value": str(len(construction_queue)),
                "detail": "Construccion derivada de memoria real.",
                "status": "OPERATIONAL" if construction_queue else "READY",
            },
            {
                "label": "Bloqueos",
                "value": str(len(blockers)),
                "detail": "Riesgos y gaps detectados desde memoria.",
                "status": "PENDING" if blockers else "READY",
            },
            {
                "label": "Aprobaciones pendientes",
                "value": str(len(approvals)),
                "detail": "Decisiones humanas pendientes en cola FORJA.",
                "status": "PENDING" if approvals else "READY",
            },
            {
                "label": "Entregas listas",
                "value": str(len(deliveries)),
                "detail": "Evidencia, memoria y outputs registrados.",
                "status": "READY" if deliveries else "UNKNOWN",
            },
            {
                "label": "Ultima ejecucion",
                "value": activity[0]["time"] if activity else "sin actividad",
                "detail": activity[0]["event"] if activity else "Sin eventos recientes.",
                "status": "COMPLETED" if activity else "UNKNOWN",
            },
        ]

    def _services(self, memory: dict) -> list[dict]:
        profile_counts = memory.get("profile_counts", {})
        services: list[dict] = []
        for app in memory.get("registered_apps", []):
            count = int(profile_counts.get(app, 0))
            services.append(
                {
                    "name": app,
                    "status": "OPERATIONAL" if count else "UNKNOWN",
                    "detail": f"{count} documento(s) de perfil conectados.",
                }
            )
        return services

    def _construction_queue(self, memory: dict) -> list[dict]:
        registered_apps = memory.get("registered_apps", [])
        construction = memory.get("construction", [])
        queue: list[dict] = []
        for index, item in enumerate(construction[:8], start=1):
            app = self._mentioned_app(item, registered_apps) or "ECOSYSTEM"
            queue.append(
                {
                    "app": app,
                    "task": item,
                    "nextAction": "Mantener trazabilidad y convertir memoria en estado operativo visible.",
                    "status": "OPERATIONAL",
                    "priority": "alta" if index <= 2 else "media",
                    "owner": "FORJA",
                    "progress": "registrado en memoria real",
                    "blocker": "ninguno critico registrado para esta tarea",
                }
            )
        if not queue and registered_apps:
            queue.append(
                {
                    "app": "ECOSYSTEM",
                    "task": f"Coordinar apps activas: {', '.join(registered_apps)}.",
                    "nextAction": "Sincronizar memoria maestra con estado operativo por app.",
                    "status": "READY",
                    "priority": "media",
                    "owner": "FORJA",
                    "progress": "apps detectadas en memoria real",
                    "blocker": "detalle de construccion no registrado",
                }
            )
        return queue

    def _blockers(self, memory: dict) -> list[dict]:
        blockers: list[dict] = []
        for index, item in enumerate(memory.get("blockers", [])[:6], start=1):
            blockers.append(
                {
                    "id": f"memory-risk-{index}",
                    "app": self._mentioned_app(item, memory.get("registered_apps", [])) or "ECOSYSTEM",
                    "title": "Riesgo registrado en memoria",
                    "cause": item,
                    "severity": "PENDING",
                    "recommendation": "Resolver o marcar como cerrado con evidencia actualizada.",
                }
            )
        missing = memory.get("apps_missing_from_primary_memory", [])
        if missing:
            blockers.append(
                {
                    "id": "memory-master-gap",
                    "app": "ECOSYSTEM",
                    "title": "Memoria maestra incompleta",
                    "cause": "Apps existentes no reflejadas en memoria maestra: " + ", ".join(missing),
                    "severity": "PENDING",
                    "recommendation": "Actualizar memoria maestra para cerrar el gap operativo.",
                }
            )
        return blockers

    def _approvals(self, commands: list[dict]) -> list[dict]:
        approvals: list[dict] = []
        for command in commands:
            if command.get("status") != "awaiting_approval":
                continue
            approvals.append(
                {
                    "id": command.get("id"),
                    "title": command.get("command", "Decision pendiente"),
                    "impact": command.get("details") or "Requiere criterio humano antes de continuar.",
                    "requiredDecision": "aprobar, rechazar o mantener en espera",
                    "risk": command.get("governance", {}).get("risk_level", "medium"),
                    "status": "PENDING",
                }
            )
        return approvals[-8:]

    def _deliveries(self, outputs: list[dict], memory: dict) -> list[dict]:
        deliveries: list[dict] = []
        for output in outputs:
            if output.get("status") != "completed":
                continue
            logical_paths = output.get("content", {}).get("logical_outputs", []) or []
            path = logical_paths[0] if logical_paths else output.get("name", "creator-output")
            deliveries.append(
                {
                    "name": output.get("title") or output.get("name") or "FORJA output",
                    "path": path,
                    "status": "COMPLETED",
                }
            )
        sources = [memory.get("primary_source", {}), *memory.get("additional_sources", [])]
        for source in sources:
            if not source.get("exists"):
                continue
            deliveries.append(
                {
                    "name": f"Memoria conectada: {source.get('name')}",
                    "path": source.get("path"),
                    "status": "READY",
                }
            )
        return deliveries[-12:]

    def _activity(self, commands: list[dict], audit_events: list[dict]) -> list[dict]:
        activity: list[dict] = []
        for command in reversed(commands[-8:]):
            activity.append(
                {
                    "time": command.get("timestamp", ""),
                    "event": f"Comando {command.get('status', 'registrado')}",
                    "app": command.get("request_type", "FORJA"),
                    "result": self._preview(command.get("response", "")),
                }
            )
        for event in reversed(audit_events[-8:]):
            activity.append(
                {
                    "time": event.get("timestamp", ""),
                    "event": event.get("event_type", "audit_event"),
                    "app": event.get("actor", "system"),
                    "result": self._preview(event.get("payload", {})),
                }
            )
        if not activity:
            activity.append(
                {
                    "time": utc_now(),
                    "event": "ecosystem_memory.loaded",
                    "app": "FORJA",
                    "result": "Memoria real conectada al runtime snapshot.",
                }
            )
        return activity[:16]

    def _local_agent_approvals(self, dashboard: dict) -> list[dict]:
        approvals: list[dict] = []
        for task in dashboard.get("critical_approvals", []):
            approvals.append(
                {
                    "id": task.get("task_id"),
                    "title": task.get("title"),
                    "impact": f"Local Agent action requires critical approval: {task.get('task_type')}",
                    "requiredDecision": "aprobar accion critica o cancelar tarea",
                    "risk": task.get("risk_level", "critical"),
                    "status": "PENDING",
                }
            )
        for task in dashboard.get("latest_results", []):
            if task.get("status") == "awaiting_human_approval":
                approvals.append(
                    {
                        "id": task.get("task_id"),
                        "title": task.get("title"),
                        "impact": "Tarea local espera aprobacion humana.",
                        "requiredDecision": "aprobar, rechazar o mantener en espera",
                        "risk": task.get("risk_level", "high"),
                        "status": "PENDING",
                    }
                )
        return approvals[-8:]

    def _local_agent_deliveries(self, dashboard: dict) -> list[dict]:
        deliveries: list[dict] = []
        for delivery in dashboard.get("deliveries", []):
            deliveries.append(
                {
                    "name": f"Local Agent: {delivery.get('name')}",
                    "path": delivery.get("path") or delivery.get("task_id"),
                    "status": delivery.get("status", "COMPLETED"),
                }
            )
        return deliveries[-8:]

    def _local_agent_activity(self, dashboard: dict) -> list[dict]:
        return [
            {
                "time": item.get("time", ""),
                "event": item.get("event", "local_agent.event"),
                "app": "LOCAL_AGENT",
                "result": item.get("result", ""),
            }
            for item in dashboard.get("recent_activity", [])[-8:]
        ]

    def _compact_local_agent_dashboard(self, dashboard: dict) -> dict:
        return {
            "agents": dashboard.get("agents", {}),
            "tasks": dashboard.get("tasks", {}),
            "latest_results": [
                self._compact_local_agent_task(task)
                for task in dashboard.get("latest_results", [])[-6:]
            ],
            "critical_approvals": [
                self._compact_local_agent_task(task)
                for task in dashboard.get("critical_approvals", [])[-6:]
            ],
            "deliveries": dashboard.get("deliveries", [])[-8:],
            "rollbacks_available": [
                self._compact_local_agent_task(task)
                for task in dashboard.get("rollbacks_available", [])[-4:]
            ],
            "recent_activity": dashboard.get("recent_activity", [])[-8:],
        }

    def _compact_local_agent_task(self, task: dict) -> dict:
        result = task.get("result") or {}
        report = result.get("report") if isinstance(result.get("report"), dict) else {}
        target = task.get("target") if isinstance(task.get("target"), dict) else {}
        artifacts = [
            {
                "name": artifact.get("name"),
                "local_path": artifact.get("local_path"),
                "status": artifact.get("status"),
                "visible_in_human_cabin": artifact.get("visible_in_human_cabin", False),
            }
            for artifact in task.get("artifacts", [])[-4:]
            if artifact.get("visible_in_human_cabin")
        ]
        return {
            "task_id": task.get("task_id"),
            "title": task.get("title"),
            "status": task.get("status"),
            "task_type": task.get("task_type"),
            "risk_level": task.get("risk_level"),
            "priority": task.get("priority"),
            "updated_at": task.get("updated_at"),
            "completed_at": task.get("completed_at"),
            "desired_output": task.get("desired_output"),
            "target": {
                "delivery_path": target.get("delivery_path"),
                "delivery_app": target.get("delivery_app"),
            },
            "result": {
                "summary": result.get("summary"),
                "human_cabin_summary": result.get("human_cabin_summary"),
                "status": result.get("status"),
                "report": {
                    "name": report.get("name"),
                    "local_path": report.get("local_path"),
                },
            },
            "artifacts": artifacts,
        }

    def _flow(self, memory: dict, construction_queue: list[dict], approvals: list[dict], blockers: list[dict], deliveries: list[dict]) -> list[dict]:
        active_apps = memory.get("active_apps", [])
        next_detail = (
            "Actualizar memoria maestra con apps faltantes y sostener trazabilidad de entregas."
            if memory.get("apps_missing_from_primary_memory")
            else "Mantener construccion y auditoria sincronizadas con memoria real."
        )
        return [
            {
                "stage": "Memoria",
                "status": "COMPLETED" if memory.get("connected") else "BLOCKED",
                "detail": f"{len(active_apps)} apps activas y {len(memory.get('registered_apps', []))} registradas.",
            },
            {
                "stage": "Construccion",
                "status": "OPERATIONAL" if construction_queue else "READY",
                "detail": construction_queue[0]["task"] if construction_queue else "Sin tarea activa registrada.",
            },
            {
                "stage": "Entregas",
                "status": "READY" if deliveries else "UNKNOWN",
                "detail": f"{len(deliveries)} evidencia(s) disponible(s).",
            },
            {
                "stage": "Aprobaciones",
                "status": "PENDING" if approvals else "COMPLETED",
                "detail": f"{len(approvals)} decision(es) pendientes.",
            },
            {
                "stage": "Bloqueos",
                "status": "PENDING" if blockers else "COMPLETED",
                "detail": f"{len(blockers)} riesgo(s) o gap(s) operativo(s) registrados.",
            },
            {
                "stage": "Siguiente paso",
                "status": "PENDING",
                "detail": next_detail,
            },
        ]

    def _mentioned_app(self, text: str, apps: list[str]) -> str | None:
        normalized = self._normalize(text)
        for app in apps:
            if self._normalize(app) in normalized or self._normalize(app.replace("_", " ")) in normalized:
                return app
        return None

    def _normalize(self, value: str) -> str:
        return " ".join(str(value).upper().replace("_", " ").replace("-", " ").split())

    def _preview(self, value: object, limit: int = 180) -> str:
        text = " ".join(str(value).split())
        return text if len(text) <= limit else f"{text[: limit - 3]}..."


human_cabin_snapshot_service = HumanCabinSnapshotService()
