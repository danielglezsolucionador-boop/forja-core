from __future__ import annotations

import hashlib
import re
import uuid

from app.core.audit import append_audit_event, utc_now


STACK_BY_TYPE: dict[str, list[str]] = {
    "app": ["frontend React/Vite", "backend FastAPI", "PostgreSQL opcional", "typed API contract"],
    "api": ["FastAPI", "schemas", "routes", "service layer"],
    "dashboard": ["React/Vite", "cards", "analytics", "responsive UI"],
    "module": ["interfaces", "service", "tests"],
    "workflow": ["steps", "triggers", "validations"],
    "integration": ["adapter boundary", "webhook contract", "credential isolation", "audit trail"],
    "repair": ["inspection plan", "affected areas", "risk notes", "regression tests"],
    "upgrade": ["inspection plan", "affected areas", "risk notes", "migration checks"],
    "analysis": ["project inventory", "risk report", "recommendations"],
    "document": ["document outline", "source notes", "review checklist"],
}

STRUCTURE_BY_TYPE: dict[str, list[str]] = {
    "app": ["frontend shell", "backend API", "domain services", "data layer", "validation suite"],
    "api": ["api contract", "schemas", "routes", "services", "tests"],
    "dashboard": ["dashboard shell", "metric cards", "analytics panels", "responsive states", "data adapters"],
    "module": ["interface contract", "service implementation", "test suite", "integration notes"],
    "workflow": ["trigger map", "step definitions", "validation gates", "notification plan", "audit trail"],
    "integration": ["adapter contract", "webhook mapping", "retry policy", "secret boundary", "audit trail"],
    "repair": ["inspection report", "affected areas map", "repair plan", "rollback notes", "regression checklist"],
    "upgrade": ["current-state review", "affected areas map", "upgrade plan", "migration notes", "regression checklist"],
    "analysis": ["project inventory", "risk map", "recommendation set", "decision log"],
    "document": ["outline", "source references", "draft sections", "review checklist"],
}

SCREENS_BY_TYPE: dict[str, list[str]] = {
    "app": ["Overview", "Records list", "Record detail", "Create/edit form", "Audit view"],
    "api": ["OpenAPI documentation", "Health check view", "Request examples"],
    "dashboard": ["Executive overview", "Metric detail", "Filters", "Alerts", "Export view"],
    "module": ["Module status", "Configuration", "Test results"],
    "workflow": ["Workflow board", "Step detail", "Approval queue", "Execution history"],
    "integration": ["Connection status", "Webhook logs", "Mapping review"],
    "repair": ["Inspection report", "Affected files view", "Risk review"],
    "upgrade": ["Upgrade report", "Compatibility matrix", "Risk review"],
    "analysis": ["Project inventory", "Risk report", "Recommendations"],
    "document": ["Document outline", "Review state"],
}

DOMAIN_MODULES: dict[str, list[str]] = {
    "inventario": ["inventory_items", "stock_movements", "warehouse_summary"],
    "ventas": ["sales_pipeline", "orders", "revenue_metrics"],
    "clientes": ["customer_records", "customer_segments", "customer_permissions"],
    "financiero": ["financial_metrics", "margin_controls", "budget_tracking"],
    "contable": ["ledger_records", "accounting_exports", "reconciliation"],
    "tributario": ["tax_rules", "filing_calendar", "compliance_checks"],
    "WhatsApp": ["whatsapp_adapter", "message_templates", "conversation_audit"],
    "ecommerce": ["catalog", "cart", "orders"],
    "logistica": ["shipments", "route_tracking", "dispatch_queue"],
    "RRHH": ["employee_records", "roles", "payroll_summary"],
}


class ProjectBlueprintService:
    def generate(self, payload: dict) -> dict:
        interpretation = payload["interpretation"]
        source_request_id = payload.get("source_request_id") or self._source_request_id(interpretation)
        blueprint = {
            "blueprint_id": f"bp-{uuid.uuid4()}",
            "source_request_id": source_request_id,
            "sender": interpretation["sender"],
            "response_target": interpretation["response_target"],
            "project_name": self._project_name(interpretation),
            "project_type": interpretation["request_type"],
            "domain": interpretation["domain"],
            "objective": self._objective(interpretation),
            "stack_recommendation": self._stack(interpretation),
            "suggested_structure": self._suggested_structure(interpretation),
            "modules": self._modules(interpretation),
            "screens": self._screens(interpretation),
            "endpoints": self._endpoints(interpretation),
            "data_model": self._data_model(interpretation),
            "risks": self._risks(interpretation),
            "risk_level": interpretation["risk_level"],
            "approval_required": interpretation["requires_approval"],
            "construction_steps": self._construction_steps(interpretation),
            "validation_criteria": self._validation_criteria(interpretation),
            "created_at": utc_now(),
        }
        audit_risk = interpretation["risk_level"].lower()
        append_audit_event(
            "blueprint_generated",
            interpretation["sender"],
            {
                "blueprint_id": blueprint["blueprint_id"],
                "source_request_id": source_request_id,
                "project_type": blueprint["project_type"],
                "domain": blueprint["domain"],
                "response_target": blueprint["response_target"],
            },
            risk=audit_risk,
        )
        append_audit_event(
            "blueprint_ready_for_approval",
            interpretation["sender"],
            {
                "blueprint_id": blueprint["blueprint_id"],
                "approval_required": blueprint["approval_required"],
                "risk_level": blueprint["risk_level"],
                "response_target": blueprint["response_target"],
            },
            risk=audit_risk,
        )
        return blueprint

    def _source_request_id(self, interpretation: dict) -> str:
        basis = f"{interpretation['sender']}:{interpretation['normalized_input']}:{interpretation['timestamp']}"
        digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:12]
        return f"intent-{digest}"

    def _project_name(self, interpretation: dict) -> str:
        request_type = interpretation["request_type"]
        domain = interpretation["domain"]
        type_label = {
            "api": "API",
            "app": "App",
            "dashboard": "Dashboard",
            "module": "Module",
            "workflow": "Workflow",
            "integration": "Integration",
            "repair": "Repair",
            "upgrade": "Upgrade",
            "analysis": "Analysis",
            "document": "Document",
        }[request_type]
        if request_type in {"repair", "upgrade", "analysis"}:
            subject = self._repair_subject(interpretation["normalized_input"])
            return f"{subject} {type_label} Blueprint"
        if domain == "general":
            return f"FORJA {type_label} Blueprint"
        return f"{self._title(domain)} {type_label} Blueprint"

    def _objective(self, interpretation: dict) -> str:
        if interpretation["confidence"] < 0.25:
            return "Clarificar alcance antes de proponer construccion."
        if interpretation["request_type"] in {"repair", "upgrade"}:
            return f"Planificar {interpretation['request_type']} controlado sin modificar codigo todavia."
        return interpretation["objective"]

    def _stack(self, interpretation: dict) -> list[str]:
        return STACK_BY_TYPE[interpretation["request_type"]]

    def _suggested_structure(self, interpretation: dict) -> list[str]:
        return STRUCTURE_BY_TYPE[interpretation["request_type"]]

    def _modules(self, interpretation: dict) -> list[str]:
        modules = list(interpretation.get("suggested_modules", []))
        modules.extend(DOMAIN_MODULES.get(interpretation["domain"], []))
        if interpretation["request_type"] in {"repair", "upgrade"}:
            modules.extend(["inspection", "risk_register", "rollback_plan"])
        return self._dedupe(modules)

    def _screens(self, interpretation: dict) -> list[str]:
        screens = list(SCREENS_BY_TYPE[interpretation["request_type"]])
        domain = interpretation["domain"]
        if domain != "general" and interpretation["request_type"] in {"app", "dashboard"}:
            screens.insert(0, f"{self._title(domain)} overview")
        return self._dedupe(screens)

    def _endpoints(self, interpretation: dict) -> list[dict]:
        request_type = interpretation["request_type"]
        resource = self._resource_name(interpretation)
        if request_type == "api":
            return [
                {"method": "GET", "path": f"/{resource}", "purpose": f"Listar registros de {resource}."},
                {"method": "POST", "path": f"/{resource}", "purpose": f"Registrar un nuevo recurso de {resource}."},
                {"method": "GET", "path": f"/{resource}/{{id}}", "purpose": "Consultar detalle controlado."},
            ]
        if request_type in {"app", "dashboard"}:
            return [
                {"method": "GET", "path": f"/{resource}/summary", "purpose": "Entregar resumen para pantalla principal."},
                {"method": "GET", "path": f"/{resource}/items", "purpose": "Entregar registros filtrables."},
            ]
        if request_type == "workflow":
            return [
                {"method": "POST", "path": f"/workflows/{resource}/trigger", "purpose": "Iniciar workflow con validaciones."},
                {"method": "GET", "path": f"/workflows/{resource}/runs", "purpose": "Revisar historial de ejecucion."},
            ]
        if request_type == "integration":
            return [
                {"method": "POST", "path": f"/integrations/{resource}/webhook", "purpose": "Recibir evento externo controlado."},
                {"method": "GET", "path": f"/integrations/{resource}/status", "purpose": "Revisar estado de conexion."},
            ]
        if request_type in {"repair", "upgrade", "analysis"}:
            return [{"method": "GET", "path": f"/analysis/{resource}/report", "purpose": "Consultar reporte de inspeccion propuesto."}]
        return [{"method": "GET", "path": f"/documents/{resource}/outline", "purpose": "Consultar outline propuesto."}]

    def _data_model(self, interpretation: dict) -> list[dict]:
        domain = interpretation["domain"]
        request_type = interpretation["request_type"]
        if request_type in {"repair", "upgrade", "analysis"}:
            return [
                {"name": "InspectionFinding", "fields": ["id", "area", "severity", "evidence", "recommendation"], "purpose": "Registrar hallazgos antes de modificar codigo."},
                {"name": "RiskNote", "fields": ["id", "risk_level", "affected_area", "mitigation"], "purpose": "Mantener trazabilidad de riesgo."},
            ]
        entity = {
            "inventario": ("InventoryItem", ["id", "sku", "name", "stock", "warehouse", "status"]),
            "ventas": ("SaleRecord", ["id", "customer_id", "amount", "stage", "owner", "created_at"]),
            "clientes": ("Customer", ["id", "name", "segment", "contact", "status", "created_at"]),
            "financiero": ("FinancialMetric", ["id", "period", "revenue", "margin", "cashflow", "variance"]),
            "contable": ("LedgerEntry", ["id", "account", "debit", "credit", "period", "source"]),
            "tributario": ("TaxObligation", ["id", "period", "tax_type", "amount", "due_date", "status"]),
            "WhatsApp": ("WhatsAppConversation", ["id", "contact", "template", "status", "last_message_at"]),
            "ecommerce": ("Order", ["id", "customer_id", "items", "total", "payment_status", "fulfillment_status"]),
            "logistica": ("Shipment", ["id", "origin", "destination", "carrier", "status", "eta"]),
            "RRHH": ("Employee", ["id", "name", "role", "team", "status", "start_date"]),
            "general": ("ProjectRecord", ["id", "name", "status", "owner", "created_at"]),
        }[domain]
        return [
            {"name": entity[0], "fields": entity[1], "purpose": f"Entidad principal para {domain}."},
            {"name": "AuditEvent", "fields": ["id", "actor", "event_type", "payload", "timestamp"], "purpose": "Trazabilidad operacional."},
        ]

    def _risks(self, interpretation: dict) -> list[dict]:
        risk_level = interpretation["risk_level"]
        risks = [
            {
                "level": risk_level,
                "title": "Inherited intent risk",
                "mitigation": "Mantener aprobacion humana y zero-write hasta una fase posterior.",
            }
        ]
        if interpretation["request_type"] in {"repair", "upgrade"}:
            risks.append(
                {
                    "level": "HIGH",
                    "title": "Existing project modification risk",
                    "mitigation": "Inspeccionar y aprobar cambios antes de tocar codigo real.",
                }
            )
        elif risk_level == "MEDIUM":
            risks.append(
                {
                    "level": "MEDIUM",
                    "title": "Scope and data assumptions",
                    "mitigation": "Confirmar alcance, modelo de datos y pantallas antes de construir.",
                }
            )
        else:
            risks.append(
                {
                    "level": "LOW",
                    "title": "Clarification risk",
                    "mitigation": "Validar el blueprint con el solicitante antes de avanzar.",
                }
            )
        return risks

    def _construction_steps(self, interpretation: dict) -> list[str]:
        request_type = interpretation["request_type"]
        if request_type in {"repair", "upgrade"}:
            return [
                "Inspeccionar proyecto existente sin modificar archivos.",
                "Mapear areas afectadas y dependencias.",
                "Preparar plan de cambio con rollback.",
                "Solicitar aprobacion antes de cualquier modificacion real.",
            ]
        return [
            "Revisar interpretacion y confirmar alcance.",
            "Validar stack, modulos y estructura sugerida.",
            "Aprobar blueprint antes de iniciar Builder.",
            "Preparar criterios de validacion para la siguiente fase.",
        ]

    def _validation_criteria(self, interpretation: dict) -> list[str]:
        criteria = [
            "Blueprint no crea carpetas ni archivos.",
            "Response target coincide con el sender original.",
            "Risk level hereda la clasificacion del intent.",
            "Aprobacion humana se mantiene antes de construccion real.",
        ]
        if interpretation["request_type"] == "api":
            criteria.append("Endpoints y schemas quedan definidos antes de implementacion.")
        if interpretation["request_type"] == "dashboard":
            criteria.append("Pantallas y metricas quedan revisadas antes de construir UI real.")
        return criteria

    def _resource_name(self, interpretation: dict) -> str:
        domain = interpretation["domain"]
        if domain == "WhatsApp":
            return "whatsapp"
        if domain == "RRHH":
            return "rrhh"
        if domain == "general":
            return self._slug(interpretation["request_type"])
        return self._slug(domain)

    def _repair_subject(self, text: str) -> str:
        for subject in ["backend", "frontend", "dashboard", "api", "app", "proyecto"]:
            if subject in text:
                return self._title(subject)
        return "Project"

    def _title(self, value: str) -> str:
        if value in {"WhatsApp", "RRHH"}:
            return value
        return value.replace("_", " ").title()

    def _slug(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "project"

    def _dedupe(self, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            if value not in result:
                result.append(value)
        return result


project_blueprint_service = ProjectBlueprintService()
