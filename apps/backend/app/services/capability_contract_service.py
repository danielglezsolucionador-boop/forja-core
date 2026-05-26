from __future__ import annotations

import uuid

from app.core.audit import append_audit_event, utc_now
from app.core.storage import JsonStore, store


PROVIDER_AGNOSTIC_CONSTRAINTS = ["provider_agnostic", "no_model_selection", "no_api_execution"]
FORBIDDEN_PROVIDER_MARKERS = {
    "openai",
    "anthropic",
    "gemini",
    "deepseek",
    "qwen",
    "gpt",
    "claude",
    "llama",
    "mistral",
    "model:",
    "provider:",
    "api_key",
    "token",
    "secret",
}
APPROVAL_CAPABILITY_TYPES = {"coding", "frontend_generation", "backend_generation", "debugging", "repair", "architecture"}


class CapabilityContractError(ValueError):
    pass


class CapabilityContractService:
    def __init__(self, state_store: JsonStore | None = None) -> None:
        self._store = state_store or store("capability_contracts")

    def create_contract(self, payload: dict) -> dict:
        self._validate_provider_independence(payload)
        constraints = self._provider_constraints(payload.get("provider_constraints", []))
        requires_human_approval = payload.get("requires_human_approval")
        if requires_human_approval is None:
            requires_human_approval = self._requires_approval(payload)

        now = utc_now()
        contract = {
            "capability_id": f"cap-{uuid.uuid4()}",
            "capability_type": payload["capability_type"],
            "reasoning_level": payload["reasoning_level"],
            "coding_level": payload["coding_level"],
            "speed_priority": payload["speed_priority"],
            "cost_priority": payload["cost_priority"],
            "context_size": payload["context_size"],
            "provider_constraints": constraints,
            "requires_human_approval": bool(requires_human_approval),
            "fallback_allowed": bool(payload["fallback_allowed"]),
            "execution_scope": payload["execution_scope"],
            "requested_by": payload["requested_by"],
            "timestamp": now,
        }

        risk = self._audit_risk(contract)
        append_audit_event(
            "capability_requested",
            contract["requested_by"],
            {
                "capability_id": contract["capability_id"],
                "capability_type": contract["capability_type"],
                "execution_scope": contract["execution_scope"],
                "fallback_allowed": contract["fallback_allowed"],
            },
            risk=risk,
        )
        append_audit_event(
            "capability_profile_generated",
            contract["requested_by"],
            {
                "capability_id": contract["capability_id"],
                "reasoning_level": contract["reasoning_level"],
                "coding_level": contract["coding_level"],
                "cost_priority": contract["cost_priority"],
                "speed_priority": contract["speed_priority"],
                "requires_human_approval": contract["requires_human_approval"],
                "provider_bound": False,
            },
            risk=risk,
        )
        self._save_contract(contract)
        return contract

    def list_contracts(self, limit: int = 100) -> list[dict]:
        records = self._records()
        return records[-limit:]

    def latest_contract(self) -> dict | None:
        records = self._records()
        return records[-1] if records else None

    def _provider_constraints(self, values: list[str]) -> list[str]:
        constraints: list[str] = []
        for value in [*values, *PROVIDER_AGNOSTIC_CONSTRAINTS]:
            clean = value.strip().lower().replace(" ", "_")
            if not clean or clean in constraints:
                continue
            constraints.append(clean)
        return constraints

    def _requires_approval(self, payload: dict) -> bool:
        return (
            payload["capability_type"] in APPROVAL_CAPABILITY_TYPES
            or payload["reasoning_level"] in {"high", "extreme"}
            or payload["cost_priority"] == "premium_allowed"
            or payload["speed_priority"] == "maximum_quality"
            or payload["fallback_allowed"] is False
        )

    def _validate_provider_independence(self, payload: dict) -> None:
        values = [
            payload.get("execution_scope", ""),
            payload.get("capability_type", ""),
            *payload.get("provider_constraints", []),
        ]
        haystack = " ".join(str(value).lower() for value in values)
        if any(marker in haystack for marker in FORBIDDEN_PROVIDER_MARKERS):
            raise CapabilityContractError("provider_specific_contract_blocked")

    def _audit_risk(self, contract: dict) -> str:
        if contract["capability_type"] == "repair" or contract["reasoning_level"] == "extreme":
            return "high"
        if contract["requires_human_approval"]:
            return "medium"
        return "low"

    def _records(self) -> list[dict]:
        payload = self._store.read({"records": []})
        return payload.get("records", [])

    def _save_contract(self, contract: dict) -> None:
        def mutator(payload: dict) -> None:
            payload.setdefault("records", []).append(contract)

        self._store.update({"records": []}, mutator)


capability_contract_service = CapabilityContractService()
