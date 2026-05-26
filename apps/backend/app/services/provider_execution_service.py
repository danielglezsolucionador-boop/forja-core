from __future__ import annotations

import uuid

from app.core.audit import append_audit_event, read_audit_events, utc_now
from app.core.storage import JsonStore, store
from app.services.capability_routing_service import capability_routing_engine


PRIMARY_FAILURE_MODES = {"provider_unavailable", "timeout", "low_confidence", "provider_disabled", "forced_failure"}
DEGRADED_FAILURE_MODES = {"timeout", "low_confidence"}

BASE_TOKENS = {
    "reasoning": 1800,
    "coding": 4200,
    "frontend_generation": 5200,
    "backend_generation": 5000,
    "debugging": 3300,
    "repair": 3800,
    "analysis": 2400,
    "summarization": 1400,
    "architecture": 3000,
    "documentation": 2200,
}
MODE_TOKEN_FACTOR = {"low_cost": 0.85, "balanced": 1.0, "premium": 1.35, "safe_mode": 0.7, "experimental": 1.12}
QUALITY_DOWNGRADE = {"extreme": "high", "high": "medium", "medium": "low", "low": "low"}
COST_RATE = {"low_cost": 0.0004, "balanced": 0.0015, "premium_allowed": 0.006}
SPEED_DURATION = {"fast": (1.1, 4200), "balanced": (2.2, 3200), "maximum_quality": (3.8, 2200)}


class ProviderExecutionSimulator:
    def __init__(self, state_store: JsonStore | None = None) -> None:
        self._store = state_store or store("provider_execution_simulations")

    def simulate(self, payload: dict) -> dict:
        contract = payload["contract"]
        failure_mode = payload.get("failure_mode", "none")
        execution_id = f"sim-{uuid.uuid4()}"
        timeline = [self._event("simulation.preparing", "Provider execution simulation prepared with real routing inputs.")]
        risk = self._risk(contract, payload.get("routing_plan"))

        append_audit_event(
            "execution_started",
            contract["requested_by"],
            {
                "execution_id": execution_id,
                "capability_id": contract["capability_id"],
                "capability_type": contract["capability_type"],
                "simulation_only": True,
                "external_request_executed": False,
            },
            risk=risk,
        )

        plan = payload.get("routing_plan") or capability_routing_engine.create_plan(
            {"contract": contract, "disabled_provider_ids": payload.get("disabled_provider_ids", [])}
        )
        timeline.append(self._event("routing.completed", f"Routing plan {plan['plan_id']} completed before simulated execution."))
        primary = plan.get("primary_provider")
        fallback_chain = list(plan.get("fallback_tree") or [])
        timeline.append(self._event("provider.selected", self._provider_detail(primary)))

        if not primary:
            return self._failed_result(
                execution_id=execution_id,
                contract=contract,
                plan=plan,
                primary=None,
                fallback_chain=fallback_chain,
                timeline=timeline,
                failure_mode=failure_mode,
                reason="No compatible provider profile was selected for simulation.",
                risk=risk,
            )

        append_audit_event(
            "provider_execution_started",
            contract["requested_by"],
            {
                "execution_id": execution_id,
                "capability_id": contract["capability_id"],
                "provider_id": primary["provider_id"],
                "simulation_only": True,
            },
            risk=risk,
        )
        timeline.append(self._event("execution.started", f"Simulated execution started on {primary['provider_id']}."))

        provider_used = primary
        fallback_used = None
        fallback_triggered = False
        status = "completed"
        effective_failure_mode = failure_mode

        if self._primary_failed(failure_mode, primary, plan):
            timeline.append(self._event("execution.primary_failed", self._failure_detail(failure_mode, primary)))
            if failure_mode == "none":
                effective_failure_mode = "provider_unavailable"
            if failure_mode != "forced_failure" and contract["fallback_allowed"] and fallback_chain:
                fallback_triggered = True
                fallback_used = fallback_chain[0]
                provider_used = fallback_used
                status = "degraded_mode" if effective_failure_mode in DEGRADED_FAILURE_MODES else "completed"
                timeline.append(self._event("fallback.triggered", f"Fallback activated: {fallback_used['provider_id']} selected from prepared chain."))
                append_audit_event(
                    "fallback_triggered",
                    contract["requested_by"],
                    {
                        "execution_id": execution_id,
                        "capability_id": contract["capability_id"],
                        "primary_provider": primary["provider_id"],
                        "fallback_provider": fallback_used["provider_id"],
                        "failure_mode": effective_failure_mode,
                    },
                    risk=risk,
                )
                append_audit_event(
                    "provider_execution_started",
                    contract["requested_by"],
                    {
                        "execution_id": execution_id,
                        "capability_id": contract["capability_id"],
                        "provider_id": fallback_used["provider_id"],
                        "simulation_only": True,
                        "fallback": True,
                    },
                    risk=risk,
                )
            else:
                return self._failed_result(
                    execution_id=execution_id,
                    contract=contract,
                    plan=plan,
                    primary=primary,
                    fallback_chain=fallback_chain,
                    timeline=timeline,
                    failure_mode=effective_failure_mode,
                    reason="Primary simulated provider failed and no fallback execution was available.",
                    risk=risk,
                )

        estimates = self._estimates(contract, plan, provider_used, fallback_triggered)
        simulated_quality = self._quality(provider_used, status)
        summary = self._summary(contract["capability_type"], provider_used, status, fallback_triggered)
        outputs = self._outputs(contract["capability_type"], summary, fallback_triggered, effective_failure_mode)
        timeline.append(self._event("execution.completed" if status == "completed" else "execution.degraded_mode", summary))
        result = {
            "execution_id": execution_id,
            "capability_id": contract["capability_id"],
            "routing_plan_id": plan["plan_id"],
            "provider_used": provider_used,
            "primary_provider_attempted": primary,
            "fallback_provider_used": fallback_used,
            "fallback_chain": fallback_chain,
            "capability_type": contract["capability_type"],
            "execution_mode": plan["execution_mode"],
            "estimated_tokens": estimates["tokens"],
            "estimated_cost": estimates["cost"],
            "estimated_duration": estimates["duration"],
            "simulated_quality": simulated_quality,
            "generated_summary": summary,
            "execution_status": status,
            "fallback_triggered": fallback_triggered,
            "failure_mode": effective_failure_mode,
            "estimated_cost_profile": provider_used["cost_profile"],
            "outputs": outputs,
            "timeline": timeline,
            "audit_events": [],
            "external_request_executed": False,
            "generated_at": utc_now(),
        }
        append_audit_event(
            "execution_completed",
            contract["requested_by"],
            {
                "execution_id": execution_id,
                "capability_id": contract["capability_id"],
                "provider_used": provider_used["provider_id"],
                "execution_status": status,
                "outputs": len(outputs),
                "external_request_executed": False,
            },
            risk=risk,
        )
        return self._save_and_enrich(result)

    def latest(self) -> dict | None:
        records = self._records()
        return self._with_audit_preview(records[-1]) if records else None

    def _primary_failed(self, failure_mode: str, primary: dict, plan: dict) -> bool:
        if failure_mode in PRIMARY_FAILURE_MODES:
            return True
        if not primary.get("enabled", True):
            return True
        if str(primary.get("availability_status", "")).startswith("disabled"):
            return True
        return float(plan.get("confidence", 0.0)) < 0.2

    def _failed_result(
        self,
        *,
        execution_id: str,
        contract: dict,
        plan: dict,
        primary: dict | None,
        fallback_chain: list[dict],
        timeline: list[dict],
        failure_mode: str,
        reason: str,
        risk: str,
    ) -> dict:
        estimates = self._estimates(contract, plan, primary, False)
        timeline.append(self._event("execution.failed", reason))
        result = {
            "execution_id": execution_id,
            "capability_id": contract["capability_id"],
            "routing_plan_id": plan.get("plan_id"),
            "provider_used": None,
            "primary_provider_attempted": primary,
            "fallback_provider_used": None,
            "fallback_chain": fallback_chain,
            "capability_type": contract["capability_type"],
            "execution_mode": plan.get("execution_mode", "safe_mode"),
            "estimated_tokens": estimates["tokens"],
            "estimated_cost": 0.0,
            "estimated_duration": estimates["duration"],
            "simulated_quality": None,
            "generated_summary": reason,
            "execution_status": "failed",
            "fallback_triggered": False,
            "failure_mode": failure_mode,
            "estimated_cost_profile": None,
            "outputs": [
                {
                    "kind": "failure_report",
                    "label": "simulated failure report",
                    "summary": reason,
                    "status": "failed",
                    "source": "provider_execution_simulator",
                }
            ],
            "timeline": timeline,
            "audit_events": [],
            "external_request_executed": False,
            "generated_at": utc_now(),
        }
        append_audit_event(
            "execution_failed",
            contract["requested_by"],
            {
                "execution_id": execution_id,
                "capability_id": contract["capability_id"],
                "failure_mode": failure_mode,
                "reason": reason,
                "external_request_executed": False,
            },
            risk=risk,
        )
        return self._save_and_enrich(result)

    def _estimates(self, contract: dict, plan: dict, provider: dict | None, fallback_triggered: bool) -> dict:
        base = BASE_TOKENS.get(contract["capability_type"], 2000)
        mode = plan.get("execution_mode", "balanced")
        context_factor = min(1.35, max(0.75, contract["context_size"] / 64000))
        tokens = int(base * MODE_TOKEN_FACTOR.get(mode, 1.0) * context_factor)
        if fallback_triggered:
            tokens = int(tokens * 1.12)
        cost_profile = provider["cost_profile"] if provider else "low_cost"
        cost = round((tokens / 1000) * COST_RATE[cost_profile], 4)
        speed_profile = provider["speed_profile"] if provider else "fast"
        floor, divisor = SPEED_DURATION[speed_profile]
        duration = round(floor + (tokens / divisor) + (1.4 if fallback_triggered else 0), 2)
        return {"tokens": tokens, "cost": cost, "duration": duration}

    def _quality(self, provider: dict, status: str) -> str:
        quality = provider["reasoning_strength"]
        if status == "degraded_mode":
            return QUALITY_DOWNGRADE[quality]
        return quality

    def _summary(self, capability_type: str, provider: dict, status: str, fallback_triggered: bool) -> str:
        summaries = {
            "reasoning": "Reasoning trace prepared",
            "coding": "Controlled code generation outline prepared",
            "frontend_generation": "React dashboard structure prepared",
            "backend_generation": "FastAPI routes generated",
            "debugging": "Debugging path and candidate fixes prepared",
            "repair": "Potential architecture issues detected",
            "analysis": "Operational analysis summary prepared",
            "summarization": "Condensed operational summary prepared",
            "architecture": "Microservice-ready structure recommended",
            "documentation": "Technical documentation draft prepared",
        }
        prefix = "Fallback simulation completed" if fallback_triggered else "Provider simulation completed"
        suffix = " in degraded mode" if status == "degraded_mode" else ""
        return f"{prefix} with {provider['provider_name']}{suffix}: {summaries.get(capability_type, 'Operational result prepared')}."

    def _outputs(self, capability_type: str, summary: str, fallback_triggered: bool, failure_mode: str) -> list[dict]:
        output_kind = {
            "reasoning": "reasoning_summary",
            "coding": "code_generation",
            "frontend_generation": "frontend_generation",
            "backend_generation": "backend_generation",
            "debugging": "repair_findings",
            "repair": "repair_findings",
            "analysis": "reasoning_summary",
            "summarization": "reasoning_summary",
            "architecture": "architecture_plan",
            "documentation": "documentation_draft",
        }.get(capability_type, "reasoning_summary")
        outputs = [
            {
                "kind": output_kind,
                "label": output_kind.replace("_", " "),
                "summary": summary,
                "status": "simulated",
                "source": "provider_execution_simulator",
            }
        ]
        if fallback_triggered:
            outputs.append(
                {
                    "kind": "fallback_report",
                    "label": "fallback execution report",
                    "summary": f"Fallback activated after simulated {failure_mode}.",
                    "status": "simulated",
                    "source": "provider_execution_simulator",
                }
            )
        return outputs

    def _provider_detail(self, provider: dict | None) -> str:
        if not provider:
            return "No provider profile available for simulated execution."
        return f"{provider['provider_id']} selected for simulated execution."

    def _failure_detail(self, failure_mode: str, provider: dict) -> str:
        details = {
            "provider_unavailable": "provider unavailable",
            "timeout": "simulated timeout",
            "low_confidence": "low confidence threshold",
            "provider_disabled": "provider disabled",
            "forced_failure": "forced failure simulation",
            "none": "provider became unavailable during simulation",
        }
        return f"{provider['provider_id']} failed due to {details.get(failure_mode, failure_mode)}."

    def _risk(self, contract: dict, plan: dict | None) -> str:
        if plan and plan.get("risk_level"):
            return str(plan["risk_level"]).lower()
        if contract["capability_type"] == "repair" or contract["reasoning_level"] == "extreme":
            return "high"
        if contract["requires_human_approval"]:
            return "medium"
        return "low"

    def _records(self) -> list[dict]:
        payload = self._store.read({"records": []})
        return payload.get("records", [])

    def _save_and_enrich(self, result: dict) -> dict:
        def mutator(payload: dict) -> None:
            payload.setdefault("records", []).append(result)

        self._store.update({"records": []}, mutator)
        return self._with_audit_preview(result)

    def _with_audit_preview(self, result: dict) -> dict:
        event_types = {
            "execution_started",
            "provider_execution_started",
            "fallback_triggered",
            "execution_completed",
            "execution_failed",
        }
        preview = []
        for event in read_audit_events(240):
            payload = event.get("payload", {})
            if event["event_type"] in event_types and payload.get("execution_id") == result["execution_id"]:
                preview.append(
                    {
                        "event_type": event["event_type"],
                        "actor": event["actor"],
                        "risk": event["risk"],
                        "timestamp": event["timestamp"],
                    }
                )
        enriched = dict(result)
        enriched["audit_events"] = preview[-12:]
        return enriched

    def _event(self, event: str, detail: str) -> dict:
        return {"timestamp": utc_now(), "event": event, "detail": detail}


provider_execution_simulator = ProviderExecutionSimulator()
