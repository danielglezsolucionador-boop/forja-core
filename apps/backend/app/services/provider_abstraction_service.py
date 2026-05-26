from __future__ import annotations

from app.core.audit import append_audit_event


NEUTRAL_CONSTRAINTS = {"provider_agnostic", "no_model_selection", "no_api_execution"}
QUALITY_VALUES = {"low": 0.35, "medium": 0.6, "high": 0.85, "extreme": 1.0, "none": 0.25, "expert": 1.0}


MOCK_PROVIDER_PROFILES: list[dict] = [
    {
        "provider_id": "anthropic",
        "provider_name": "Anthropic",
        "supported_capabilities": ["reasoning", "analysis", "summarization", "architecture", "documentation", "debugging", "repair"],
        "reasoning_strength": "extreme",
        "coding_strength": "medium",
        "speed_profile": "maximum_quality",
        "cost_profile": "premium_allowed",
        "context_capacity": 200000,
        "availability_status": "simulated_profile_only",
        "fallback_priority": 2,
        "premium_provider": True,
        "local_provider": False,
        "enabled": True,
        "notes": "Mock profile for future routing; no API is connected.",
    },
    {
        "provider_id": "openai",
        "provider_name": "OpenAI",
        "supported_capabilities": [
            "reasoning",
            "coding",
            "frontend_generation",
            "backend_generation",
            "debugging",
            "repair",
            "analysis",
            "summarization",
            "architecture",
            "documentation",
        ],
        "reasoning_strength": "high",
        "coding_strength": "high",
        "speed_profile": "balanced",
        "cost_profile": "premium_allowed",
        "context_capacity": 128000,
        "availability_status": "simulated_profile_only",
        "fallback_priority": 1,
        "premium_provider": True,
        "local_provider": False,
        "enabled": True,
        "notes": "Mock profile for future routing; no API is connected.",
    },
    {
        "provider_id": "gemini",
        "provider_name": "Gemini",
        "supported_capabilities": ["reasoning", "frontend_generation", "analysis", "summarization", "architecture", "documentation"],
        "reasoning_strength": "high",
        "coding_strength": "medium",
        "speed_profile": "fast",
        "cost_profile": "balanced",
        "context_capacity": 1000000,
        "availability_status": "simulated_profile_only",
        "fallback_priority": 3,
        "premium_provider": False,
        "local_provider": False,
        "enabled": True,
        "notes": "Mock profile for future routing; no API is connected.",
    },
    {
        "provider_id": "deepseek",
        "provider_name": "DeepSeek",
        "supported_capabilities": ["coding", "backend_generation", "debugging", "analysis", "summarization"],
        "reasoning_strength": "medium",
        "coding_strength": "high",
        "speed_profile": "balanced",
        "cost_profile": "low_cost",
        "context_capacity": 64000,
        "availability_status": "simulated_profile_only",
        "fallback_priority": 4,
        "premium_provider": False,
        "local_provider": False,
        "enabled": True,
        "notes": "Mock profile for future routing; no API is connected.",
    },
    {
        "provider_id": "qwen",
        "provider_name": "Qwen",
        "supported_capabilities": ["coding", "backend_generation", "debugging", "analysis", "summarization", "documentation"],
        "reasoning_strength": "medium",
        "coding_strength": "high",
        "speed_profile": "fast",
        "cost_profile": "low_cost",
        "context_capacity": 128000,
        "availability_status": "simulated_profile_only",
        "fallback_priority": 5,
        "premium_provider": False,
        "local_provider": False,
        "enabled": True,
        "notes": "Mock profile for future routing; no API is connected.",
    },
    {
        "provider_id": "local_llm",
        "provider_name": "Local LLM",
        "supported_capabilities": ["reasoning", "coding", "analysis", "summarization", "documentation"],
        "reasoning_strength": "low",
        "coding_strength": "medium",
        "speed_profile": "fast",
        "cost_profile": "low_cost",
        "context_capacity": 32000,
        "availability_status": "local_simulated_profile_only",
        "fallback_priority": 6,
        "premium_provider": False,
        "local_provider": True,
        "enabled": True,
        "notes": "Mock local profile for future offline routing; no model is executed.",
    },
]


class ProviderAbstractionService:
    def profiles(self) -> list[dict]:
        return [dict(profile) for profile in MOCK_PROVIDER_PROFILES]

    def route(self, contract: dict) -> dict:
        append_audit_event(
            "provider_matching_started",
            contract["requested_by"],
            {
                "capability_id": contract["capability_id"],
                "capability_type": contract["capability_type"],
                "fallback_allowed": contract["fallback_allowed"],
            },
            risk=self._audit_risk(contract),
        )

        scored = [self._score(profile, contract) for profile in self.profiles() if self._is_compatible(profile, contract)]
        scored.sort(key=lambda item: (-item["compatibility_score"], item["fallback_priority"], item["provider_id"]))
        compatible_profiles = [item["profile"] for item in scored]
        scoring = [{key: value for key, value in item.items() if key not in {"profile", "fallback_priority"}} for item in scored]

        selected = compatible_profiles[0] if compatible_profiles else None
        fallback = compatible_profiles[1] if contract["fallback_allowed"] and len(compatible_profiles) > 1 else None
        decision = {
            "selected_provider": selected,
            "fallback_provider": fallback,
            "reason": self._decision_reason(contract, selected, fallback),
            "confidence": round(scored[0]["compatibility_score"], 3) if scored else 0.0,
            "estimated_cost_profile": selected["cost_profile"] if selected else None,
            "estimated_quality_profile": selected["reasoning_strength"] if selected else None,
            "compatible_providers": compatible_profiles,
            "scoring": scoring,
            "fallback_strategy": self._fallback_strategy(contract, fallback),
            "external_request_executed": False,
        }

        append_audit_event(
            "provider_selected",
            contract["requested_by"],
            {
                "capability_id": contract["capability_id"],
                "selected_provider": selected["provider_id"] if selected else None,
                "compatible_count": len(compatible_profiles),
                "confidence": decision["confidence"],
                "external_request_executed": False,
            },
            risk=self._audit_risk(contract),
        )
        append_audit_event(
            "fallback_prepared",
            contract["requested_by"],
            {
                "capability_id": contract["capability_id"],
                "fallback_provider": fallback["provider_id"] if fallback else None,
                "fallback_allowed": contract["fallback_allowed"],
                "strategy": decision["fallback_strategy"],
            },
            risk=self._audit_risk(contract),
        )
        return decision

    def _is_compatible(self, profile: dict, contract: dict) -> bool:
        if not profile["enabled"]:
            return False
        if contract["capability_type"] not in profile["supported_capabilities"]:
            return False
        if profile["context_capacity"] < contract["context_size"]:
            return False
        constraints = {str(item).lower() for item in contract.get("provider_constraints", [])}
        active_constraints = constraints - NEUTRAL_CONSTRAINTS
        if "local_only" in active_constraints and not profile["local_provider"]:
            return False
        if "premium_only" in active_constraints and not profile["premium_provider"]:
            return False
        if "low_cost_only" in active_constraints and profile["cost_profile"] != "low_cost":
            return False
        allowed = {"local_only", "premium_only", "low_cost_only"}
        if active_constraints - allowed:
            return False
        return True

    def _score(self, profile: dict, contract: dict) -> dict:
        quality_score = self._quality_score(profile, contract)
        cost_score = self._cost_score(profile["cost_profile"], contract["cost_priority"])
        speed_score = self._speed_score(profile["speed_profile"], contract["speed_priority"])
        context_score = 1.0 if profile["context_capacity"] >= contract["context_size"] else 0.0
        compatibility_score = round((quality_score * 0.45) + (cost_score * 0.2) + (speed_score * 0.2) + (context_score * 0.15), 3)
        return {
            "provider_id": profile["provider_id"],
            "provider_name": profile["provider_name"],
            "quality_score": round(quality_score, 3),
            "cost_score": round(cost_score, 3),
            "speed_score": round(speed_score, 3),
            "compatibility_score": round(compatibility_score, 3),
            "reason": self._score_reason(profile, contract),
            "fallback_priority": profile["fallback_priority"],
            "profile": profile,
        }

    def _quality_score(self, profile: dict, contract: dict) -> float:
        reasoning_fit = min(QUALITY_VALUES[profile["reasoning_strength"]] / QUALITY_VALUES[contract["reasoning_level"]], 1.0)
        if contract["coding_level"] == "none":
            return reasoning_fit
        coding_fit = min(QUALITY_VALUES[profile["coding_strength"]] / QUALITY_VALUES[contract["coding_level"]], 1.0)
        return (reasoning_fit * 0.45) + (coding_fit * 0.55)

    def _cost_score(self, profile_cost: str, preferred_cost: str) -> float:
        if preferred_cost == "low_cost":
            return {"low_cost": 1.0, "balanced": 0.7, "premium_allowed": 0.35}[profile_cost]
        if preferred_cost == "premium_allowed":
            return {"premium_allowed": 1.0, "balanced": 0.85, "low_cost": 0.65}[profile_cost]
        return {"balanced": 1.0, "low_cost": 0.85, "premium_allowed": 0.65}[profile_cost]

    def _speed_score(self, profile_speed: str, preferred_speed: str) -> float:
        if preferred_speed == "fast":
            return {"fast": 1.0, "balanced": 0.75, "maximum_quality": 0.45}[profile_speed]
        if preferred_speed == "maximum_quality":
            return {"maximum_quality": 1.0, "balanced": 0.85, "fast": 0.55}[profile_speed]
        return {"balanced": 1.0, "fast": 0.85, "maximum_quality": 0.75}[profile_speed]

    def _score_reason(self, profile: dict, contract: dict) -> str:
        return (
            f"{profile['provider_id']} supports {contract['capability_type']} with "
            f"{profile['reasoning_strength']} reasoning, {profile['coding_strength']} coding, "
            f"{profile['cost_profile']} cost, and {profile['speed_profile']} speed profile."
        )

    def _decision_reason(self, contract: dict, selected: dict | None, fallback: dict | None) -> str:
        if not selected:
            return "No simulated provider profile satisfies capability, constraints, and context requirements."
        suffix = f" Fallback prepared with {fallback['provider_id']}." if fallback else " No fallback provider will be used for this contract."
        return f"{selected['provider_id']} is the strongest simulated match for {contract['capability_type']}.{suffix}"

    def _fallback_strategy(self, contract: dict, fallback: dict | None) -> str:
        if not contract["fallback_allowed"]:
            return "disabled_by_contract"
        if fallback:
            return f"prepare_alternate_provider:{fallback['provider_id']}"
        return "no_compatible_fallback"

    def _audit_risk(self, contract: dict) -> str:
        if contract["capability_type"] == "repair" or contract["reasoning_level"] == "extreme":
            return "high"
        if contract["requires_human_approval"]:
            return "medium"
        return "low"


provider_abstraction_service = ProviderAbstractionService()
