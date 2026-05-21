from __future__ import annotations


class EcosystemService:
    def integrations(self) -> list[dict]:
        return [
            {"id": "hermes", "status": "available_for_contract_mapping", "mode": "read_only", "owner": "Hermes", "boundary": "FORJA does not modify Hermes runtime, polling, provider bridge, backend, or dashboard."},
            {"id": "cerebro", "status": "planned_contract", "mode": "metadata_only", "owner": "Cerebro", "boundary": "No invented Cerebro API dependency."},
            {"id": "centinela", "status": "planned_audit_hook", "mode": "audit_metadata", "owner": "Centinela", "boundary": "Security review remains external and human-readable."},
            {"id": "api-hub", "status": "planned_catalog", "mode": "metadata_only", "owner": "API Hub", "boundary": "No publishing without validation and approval."},
        ]


ecosystem_service = EcosystemService()
