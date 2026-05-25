from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


REQUEST_TYPE_PATTERNS: list[tuple[str, list[str]]] = [
    ("repair", ["repara", "reparar", "arregla", "arreglar", "corrige", "corregir", "fix", "bug", "broken"]),
    ("upgrade", ["mejora", "mejorar", "upgrade", "optimiza", "optimizar", "refactor", "refactoriza"]),
    ("analysis", ["analiza", "analizar", "inspecciona", "diagnostica", "revisa este proyecto", "audit"]),
    ("dashboard", ["dashboard", "tablero", "panel", "metricas", "kpi"]),
    ("api", ["api", "endpoint", "endpoints", "rest", "graphql", "route"]),
    ("workflow", ["workflow", "flujo", "proceso", "automatizacion", "automatizar"]),
    ("integration", ["integracion", "integrar", "conectar", "conexion", "webhook", "adapter", "conector"]),
    ("module", ["modulo", "module", "componente", "autenticacion", "auth", "login", "permisos"]),
    ("document", ["documento", "documentacion", "docs", "readme", "manual", "politica"]),
    ("app", ["app", "aplicacion", "sistema", "plataforma", "frontend"]),
]

DOMAIN_PATTERNS: list[tuple[str, list[str]]] = [
    ("inventario", ["inventario", "stock", "almacen", "existencias"]),
    ("ventas", ["ventas", "venta", "comercial", "leads"]),
    ("clientes", ["clientes", "cliente", "crm", "customer"]),
    ("financiero", ["financiero", "finanzas", "margen", "cashflow", "caja", "presupuesto"]),
    ("contable", ["contable", "contabilidad", "asientos", "libro contable"]),
    ("tributario", ["tributario", "tributaria", "impuestos", "sunat", "igv", "iva", "fiscal"]),
    ("WhatsApp", ["whatsapp", "wa business"]),
    ("ecommerce", ["ecommerce", "e-commerce", "tienda online", "carrito", "checkout"]),
    ("logistica", ["logistica", "envios", "despacho", "rutas", "transporte"]),
    ("RRHH", ["rrhh", "recursos humanos", "nomina", "empleados", "personal"]),
]

ACTION_MARKERS = [
    "crea",
    "crear",
    "creame",
    "construye",
    "construir",
    "genera",
    "generar",
    "disena",
    "disenar",
    "arma",
    "armar",
    "repara",
    "mejora",
    "analiza",
    "integra",
    "documenta",
]

HIGH_RISK_MARKERS = [
    "modifica",
    "modificar",
    "proyecto existente",
    "codigo real",
    "overwrite",
    "sobrescribe",
    "sobrescribir",
    "produccion",
    "production",
    "database",
    "base de datos",
    "deploy",
]

LOW_RISK_MARKERS = ["blueprint", "docs", "documentacion", "documento", "analiza", "analizar"]

SUGGESTED_MODULES_BY_TYPE: dict[str, list[str]] = {
    "app": ["frontend", "backend", "database", "auth", "audit"],
    "api": ["api_contract", "routes", "schemas", "auth", "audit"],
    "dashboard": ["dashboard_ui", "metrics", "charts", "filters", "exports"],
    "module": ["module_contract", "service_layer", "tests", "audit"],
    "workflow": ["workflow_steps", "approval_gate", "notifications", "audit"],
    "integration": ["adapter", "webhook_boundary", "credential_boundary", "audit"],
    "repair": ["diagnostics", "test_suite", "change_plan", "rollback_plan"],
    "upgrade": ["assessment", "migration_plan", "regression_tests", "approval_gate"],
    "analysis": ["project_inventory", "risk_report", "recommendations"],
    "document": ["document_outline", "source_notes", "review_checklist"],
}

DOMAIN_MODULES: dict[str, list[str]] = {
    "inventario": ["inventory_items", "stock_movements"],
    "ventas": ["sales_pipeline", "revenue_metrics"],
    "clientes": ["customer_records", "customer_permissions"],
    "financiero": ["financial_metrics", "margin_controls"],
    "contable": ["ledger_records", "accounting_exports"],
    "tributario": ["tax_rules", "filing_calendar"],
    "WhatsApp": ["whatsapp_adapter", "message_templates"],
    "ecommerce": ["catalog", "cart", "orders"],
    "logistica": ["shipments", "route_tracking"],
    "RRHH": ["employee_records", "roles"],
}


@dataclass(frozen=True)
class ParsedIntent:
    request_type: str
    domain: str
    objective: str
    suggested_modules: list[str]
    risk_level: str
    requires_approval: bool
    normalized_input: str
    confidence: float


def normalize_intent_input(value: str) -> str:
    lowered = value.strip().lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    without_accents = "".join(character for character in decomposed if not unicodedata.combining(character))
    return re.sub(r"\s+", " ", without_accents).strip()


def parse_intent(raw_input: str) -> ParsedIntent:
    normalized = normalize_intent_input(raw_input)
    request_type, type_matched = _detect_request_type(normalized)
    domain, domain_matched = _detect_domain(normalized)
    risk_level = _detect_risk_level(normalized, request_type)
    requires_approval = risk_level in {"MEDIUM", "HIGH"}
    confidence = _confidence(normalized, type_matched, domain_matched)
    return ParsedIntent(
        request_type=request_type,
        domain=domain,
        objective=_objective(request_type, domain, confidence),
        suggested_modules=_suggested_modules(request_type, domain, confidence),
        risk_level=risk_level,
        requires_approval=requires_approval,
        normalized_input=normalized,
        confidence=confidence,
    )


def _detect_request_type(text: str) -> tuple[str, bool]:
    for request_type, markers in REQUEST_TYPE_PATTERNS:
        if any(marker in text for marker in markers):
            return request_type, True
    return "analysis", False


def _detect_domain(text: str) -> tuple[str, bool]:
    for domain, markers in DOMAIN_PATTERNS:
        if any(marker in text for marker in markers):
            return domain, True
    return "general", False


def _detect_risk_level(text: str, request_type: str) -> str:
    if request_type in {"repair", "upgrade"}:
        return "HIGH"
    if any(marker in text for marker in HIGH_RISK_MARKERS):
        return "HIGH"
    if request_type in {"app", "api", "dashboard", "module", "workflow", "integration"}:
        return "MEDIUM"
    if request_type in {"document", "analysis"} or any(marker in text for marker in LOW_RISK_MARKERS):
        return "LOW"
    return "LOW"


def _confidence(text: str, type_matched: bool, domain_matched: bool) -> float:
    score = 0.1
    if type_matched:
        score += 0.4
    if domain_matched:
        score += 0.25
    if any(marker in text for marker in ACTION_MARKERS):
        score += 0.15
    if len(text) >= 12:
        score += 0.1
    if not type_matched and not domain_matched:
        return min(round(score, 2), 0.2)
    return min(round(score, 2), 1.0)


def _objective(request_type: str, domain: str, confidence: float) -> str:
    if confidence < 0.25:
        return "Clarificar la solicitud antes de planificar."
    if domain == "general":
        return f"Interpretar solicitud de tipo {request_type}."
    return f"Interpretar solicitud de tipo {request_type} para dominio {domain}."


def _suggested_modules(request_type: str, domain: str, confidence: float) -> list[str]:
    if confidence < 0.25:
        return ["clarification_questions"]
    modules = list(SUGGESTED_MODULES_BY_TYPE.get(request_type, ["analysis_notes"]))
    modules.extend(DOMAIN_MODULES.get(domain, []))
    deduplicated: list[str] = []
    for module in modules:
        if module not in deduplicated:
            deduplicated.append(module)
    return deduplicated
