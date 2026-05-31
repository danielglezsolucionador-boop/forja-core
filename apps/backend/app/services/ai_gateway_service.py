from __future__ import annotations

from app.core.audit import append_audit_event, utc_now
from app.core.storage import JsonStore, store
from app.services.capability_routing_service import capability_routing_engine
from app.services.provider_abstraction_service import MOCK_PROVIDER_PROFILES
from app.services.provider_priority_service import annotate_provider, economic_provider_ids, premium_provider_ids


CAPABILITY_REGISTRY = [
    "reasoning",
    "coding",
    "frontend_generation",
    "backend_generation",
    "debugging",
    "repair",
    "architecture",
    "analysis",
    "summarization",
    "documentation",
]
AVAILABLE_STATES = {"active", "degraded"}
BLOCKED_STATES = {"unavailable", "disabled", "maintenance"}


class AIGatewayError(ValueError):
    pass


class AIGatewayManager:
    def __init__(self, state_store: JsonStore | None = None) -> None:
        self._store = state_store or store("ai_gateway")

    def snapshot(self) -> dict:
        payload = self._ensure_initialized()
        return self._snapshot(payload)

    def lookup_capability(self, capability_type: str) -> dict:
        payload = self._ensure_initialized()
        if capability_type not in CAPABILITY_REGISTRY:
            raise AIGatewayError("capability_not_registered")
        capability = self._capability_entry(payload, capability_type)
        providers = [payload["providers"][provider_id] for provider_id in capability["provider_ids"]]
        return {
            "capability": capability,
            "providers": providers,
            "fallback_tree": capability["fallback_provider_ids"],
            "external_request_executed": False,
        }

    def disable_provider(self, provider_id: str) -> dict:
        return self._update_provider_state(provider_id, "disabled", audit_event="provider_disabled", enabled=False)

    def enable_provider(self, provider_id: str) -> dict:
        return self._update_provider_state(provider_id, "active", audit_event="provider_enabled", enabled=True)

    def update_health(self, provider_id: str, update: dict) -> dict:
        state = update["health_state"]
        enabled = False if state == "disabled" else None
        return self._update_provider_state(
            provider_id,
            state,
            audit_event="provider_health_changed",
            enabled=enabled,
            simulated_latency=update.get("simulated_latency"),
            simulated_failure_rate=update.get("simulated_failure_rate"),
            emit_health_audit=False,
        )

    def decision(self, payload: dict) -> dict:
        state = self._ensure_initialized()
        contract = payload["contract"]
        blocked = self._blocked_provider_ids(state)
        plan = capability_routing_engine.create_plan({"contract": contract, "disabled_provider_ids": blocked})
        health = [state["providers"][provider["provider_id"]]["health"] for provider in [plan["primary_provider"], *plan["fallback_tree"]] if provider]
        selected = plan["primary_provider"]
        reason = (
            f"AI Gateway selected {selected['provider_id']} for {contract['capability_type']} using provider registry, health state, and routing access."
            if selected
            else f"AI Gateway found no available provider for {contract['capability_type']} after health filtering."
        )
        return {
            "capability_type": contract["capability_type"],
            "selected_provider": selected,
            "fallback_provider": plan["fallback_provider"],
            "fallback_tree": plan["fallback_tree"],
            "provider_health": health,
            "routing_plan": plan,
            "decision_reason": reason,
            "availability_filter": blocked,
            "external_request_executed": False,
            "generated_at": utc_now(),
        }

    def _ensure_initialized(self) -> dict:
        def mutator(payload: dict) -> None:
            payload.setdefault("providers", {})
            payload.setdefault("timeline", [])
            payload.setdefault("registered_capabilities", [])
            initialized = bool(payload.get("initialized"))
            if not initialized:
                payload["timeline"].append(self._event("gateway.initialized", "AI Gateway initialized in simulated provider mode."))

            for profile in MOCK_PROVIDER_PROFILES:
                provider_id = profile["provider_id"]
                annotated = annotate_provider(profile, MOCK_PROVIDER_PROFILES)
                if provider_id not in payload["providers"]:
                    payload["providers"][provider_id] = self._provider_record(annotated)
                    append_audit_event(
                        "provider_registered",
                        "system",
                        {
                            "provider_id": provider_id,
                            "supported_capabilities": profile["supported_capabilities"],
                            "external_request_executed": False,
                        },
                        risk="low",
                    )
                else:
                    payload["providers"][provider_id]["provider_role"] = annotated["provider_role"]
                    payload["providers"][provider_id]["operational_priority"] = annotated["operational_priority"]
                    payload["providers"][provider_id]["supported_capabilities"] = annotated["supported_capabilities"]
                    payload["providers"][provider_id]["cost_profile"] = annotated["cost_profile"]
                    payload["providers"][provider_id]["notes"] = annotated["notes"]

            if not initialized:
                payload["timeline"].append(self._event("providers.loaded", f"{len(payload['providers'])} provider profiles loaded."))

            for capability in CAPABILITY_REGISTRY:
                if capability not in payload["registered_capabilities"]:
                    payload["registered_capabilities"].append(capability)
                    append_audit_event(
                        "capability_registered",
                        "system",
                        {"capability_type": capability, "external_request_executed": False},
                        risk="low",
                    )

            if not initialized:
                payload["timeline"].append(self._event("capability_registry.loaded", f"{len(CAPABILITY_REGISTRY)} capabilities registered."))
                payload["timeline"].append(self._event("health_states.updated", "Initial provider health snapshots prepared."))
                payload["initialized"] = True

            payload["timeline"] = payload["timeline"][-24:]

        self._store.update({"providers": {}, "timeline": [], "registered_capabilities": []}, mutator)
        return self._store.read({"providers": {}, "timeline": [], "registered_capabilities": []})

    def _provider_record(self, profile: dict) -> dict:
        state = "active" if profile["enabled"] else "disabled"
        now = utc_now()
        return {
            "provider_id": profile["provider_id"],
            "provider_name": profile["provider_name"],
            "enabled": bool(profile["enabled"]),
            "availability": state,
            "quality_profile": {
                "reasoning": profile["reasoning_strength"],
                "coding": profile["coding_strength"],
            },
            "cost_profile": profile["cost_profile"],
            "speed_profile": profile["speed_profile"],
            "supported_capabilities": profile["supported_capabilities"],
            "fallback_priority": profile["fallback_priority"],
            "premium_provider": profile["premium_provider"],
            "local_provider": profile["local_provider"],
            "provider_role": profile.get("provider_role", "balanced_future"),
            "operational_priority": int(profile.get("operational_priority", profile["fallback_priority"])),
            "health": {
                "provider_id": profile["provider_id"],
                "health_state": state,
                "simulated_latency": self._default_latency(profile),
                "simulated_failure_rate": self._default_failure_rate(profile),
                "simulated_cost_tier": profile["cost_profile"],
                "last_updated": now,
            },
            "notes": "Gateway mock provider profile; no API, model, key, or external request is connected.",
        }

    def _snapshot(self, payload: dict) -> dict:
        providers = sorted(payload["providers"].values(), key=lambda item: item["operational_priority"])
        capabilities = [self._capability_entry(payload, capability) for capability in CAPABILITY_REGISTRY]
        health = [provider["health"] for provider in providers]
        fallback_tree = {entry["capability_type"]: entry["fallback_provider_ids"] for entry in capabilities}
        gateway_status = "degraded" if any(provider["availability"] == "degraded" for provider in providers) else "active"
        economic = economic_provider_ids()
        return {
            "gateway_status": gateway_status,
            "economic_provider_id": economic[0] if economic else None,
            "premium_fallback_provider_ids": premium_provider_ids(),
            "providers": providers,
            "capabilities": capabilities,
            "health": health,
            "fallback_tree": fallback_tree,
            "execution_profiles": self._execution_profiles(),
            "timeline": payload.get("timeline", [])[-12:],
            "external_request_executed": False,
            "generated_at": utc_now(),
        }

    def _capability_entry(self, payload: dict, capability_type: str) -> dict:
        providers = [
            provider
            for provider in sorted(payload["providers"].values(), key=lambda item: item["operational_priority"])
            if capability_type in provider["supported_capabilities"]
        ]
        provider_ids = [provider["provider_id"] for provider in providers]
        available = [provider["provider_id"] for provider in providers if self._is_available(provider)]
        return {
            "capability_type": capability_type,
            "provider_ids": provider_ids,
            "available_provider_ids": available,
            "fallback_provider_ids": available[1:],
        }

    def _update_provider_state(
        self,
        provider_id: str,
        health_state: str,
        *,
        audit_event: str,
        enabled: bool | None,
        simulated_latency: int | None = None,
        simulated_failure_rate: float | None = None,
        emit_health_audit: bool = True,
    ) -> dict:
        def mutator(payload: dict) -> None:
            self._ensure_payload_initialized(payload)
            if provider_id not in payload["providers"]:
                raise AIGatewayError("provider_not_registered")
            provider = payload["providers"][provider_id]
            if enabled is not None:
                provider["enabled"] = enabled
            provider["availability"] = health_state
            provider["health"]["health_state"] = health_state
            provider["health"]["simulated_latency"] = simulated_latency if simulated_latency is not None else self._latency_for_state(provider, health_state)
            provider["health"]["simulated_failure_rate"] = (
                simulated_failure_rate if simulated_failure_rate is not None else self._failure_rate_for_state(health_state)
            )
            provider["health"]["last_updated"] = utc_now()
            payload["timeline"].append(self._event("health_states.updated", f"{provider_id} health state changed to {health_state}."))
            payload["timeline"] = payload["timeline"][-24:]
            append_audit_event(
                audit_event,
                "system",
                {"provider_id": provider_id, "health_state": health_state, "enabled": provider["enabled"], "external_request_executed": False},
                risk="medium" if health_state in BLOCKED_STATES else "low",
            )
            if emit_health_audit:
                append_audit_event(
                    "provider_health_changed",
                    "system",
                    {"provider_id": provider_id, "health_state": health_state, "external_request_executed": False},
                    risk="medium" if health_state in BLOCKED_STATES else "low",
                )

        self._store.update({"providers": {}, "timeline": [], "registered_capabilities": []}, mutator)
        return self.snapshot()

    def _ensure_payload_initialized(self, payload: dict) -> None:
        payload.setdefault("providers", {})
        payload.setdefault("timeline", [])
        payload.setdefault("registered_capabilities", [])
        if not payload["providers"]:
            for profile in MOCK_PROVIDER_PROFILES:
                payload["providers"][profile["provider_id"]] = self._provider_record(annotate_provider(profile, MOCK_PROVIDER_PROFILES))

    def _blocked_provider_ids(self, payload: dict) -> list[str]:
        return [provider_id for provider_id, provider in payload["providers"].items() if not self._is_available(provider)]

    def _is_available(self, provider: dict) -> bool:
        return bool(provider["enabled"]) and provider["availability"] in AVAILABLE_STATES

    def _execution_profiles(self) -> list[dict]:
        return [
            {"execution_mode": "low_cost", "quality_bias": "moderate", "cost_bias": "lowest_available", "speed_bias": "balanced", "fallback_policy": "prefer_low_cost_chain"},
            {"execution_mode": "balanced", "quality_bias": "balanced", "cost_bias": "balanced", "speed_bias": "balanced", "fallback_policy": "best_compatible_chain"},
            {"execution_mode": "premium", "quality_bias": "highest_available", "cost_bias": "premium_allowed", "speed_bias": "quality_first", "fallback_policy": "premium_first_chain"},
            {"execution_mode": "safe_mode", "quality_bias": "controlled", "cost_bias": "low", "speed_bias": "fast", "fallback_policy": "local_or_disabled_safe_chain"},
            {"execution_mode": "experimental", "quality_bias": "exploratory", "cost_bias": "bounded", "speed_bias": "adaptive", "fallback_policy": "explicit_approval_chain"},
        ]

    def _default_latency(self, profile: dict) -> int:
        if profile["local_provider"]:
            return 90
        if profile["speed_profile"] == "fast":
            return 260
        if profile["speed_profile"] == "balanced":
            return 420
        return 720

    def _default_failure_rate(self, profile: dict) -> float:
        if profile["local_provider"]:
            return 0.08
        if profile["premium_provider"]:
            return 0.02
        return 0.04

    def _latency_for_state(self, provider: dict, health_state: str) -> int:
        base = provider["health"]["simulated_latency"]
        if health_state == "active":
            return max(80, min(base, self._default_latency(provider)))
        if health_state == "degraded":
            return max(base, 1100)
        if health_state == "maintenance":
            return 0
        return max(base, 2000)

    def _failure_rate_for_state(self, health_state: str) -> float:
        if health_state == "active":
            return 0.02
        if health_state == "degraded":
            return 0.22
        if health_state == "maintenance":
            return 1.0
        if health_state == "unavailable":
            return 1.0
        if health_state == "disabled":
            return 1.0
        return 0.04

    def _event(self, event: str, detail: str) -> dict:
        return {"timestamp": utc_now(), "event": event, "detail": detail}


ai_gateway_manager = AIGatewayManager()
