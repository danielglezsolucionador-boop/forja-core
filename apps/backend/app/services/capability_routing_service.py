from __future__ import annotations

import uuid

from app.core.audit import append_audit_event, utc_now
from app.services.provider_abstraction_service import NEUTRAL_CONSTRAINTS, QUALITY_VALUES, provider_abstraction_service
from app.services.provider_priority_service import annotate_provider, economic_provider_ids, operational_priority


CONSTRAINTS = {"local_only", "premium_only", "low_cost_only", "safe_mode", "experimental_mode"}


class CapabilityRoutingEngine:
    def create_plan(self, payload: dict) -> dict:
        contract = payload["contract"]
        execution_mode = payload.get("execution_mode_hint") or self._execution_mode(contract)
        providers = self._profiles_with_overrides(payload.get("disabled_provider_ids", []))
        risk_level = self._risk_level(contract, execution_mode)
        timeline = [self._event("capability.analyzed", "CapabilityContract analyzed for routing factors.")]
        append_audit_event(
            "routing_started",
            contract["requested_by"],
            {
                "capability_id": contract["capability_id"],
                "capability_type": contract["capability_type"],
                "execution_mode": execution_mode,
            },
            risk=risk_level.lower(),
        )

        scored = []
        for profile in providers:
            score = self._evaluate_provider(profile, contract, execution_mode)
            append_audit_event(
                "provider_evaluated",
                contract["requested_by"],
                {
                    "capability_id": contract["capability_id"],
                    "provider_id": profile["provider_id"],
                    "compatible": score["compatible"],
                    "compatibility_score": score["compatibility_score"],
                    "reason": score["reason"],
                },
                risk=risk_level.lower(),
            )
            if score["compatible"]:
                scored.append(score)

        scored.sort(key=lambda item: self._selection_key(item, execution_mode))
        timeline.append(self._event("providers.evaluated", f"{len(providers)} provider profiles evaluated; {len(scored)} compatible."))

        primary = scored[0]["profile"] if scored else None
        fallback_tree = [item["profile"] for item in scored[1:3]] if contract["fallback_allowed"] else []
        fallback = fallback_tree[0] if fallback_tree else None
        timeline.append(self._event("provider.selected", self._selected_detail(primary)))
        timeline.append(self._event("fallback.prepared", self._fallback_detail(contract, fallback_tree)))

        provider_scores = [{key: value for key, value in item.items() if key not in {"profile", "compatible", "fallback_priority"}} for item in scored]
        plan = {
            "plan_id": f"route-{uuid.uuid4()}",
            "capability_id": contract["capability_id"],
            "primary_provider": primary,
            "fallback_provider": fallback,
            "fallback_tree": fallback_tree,
            "routing_reason": self._routing_reason(contract, primary, fallback_tree, execution_mode),
            "estimated_quality": primary["reasoning_strength"] if primary else None,
            "estimated_cost": primary["cost_profile"] if primary else None,
            "estimated_speed": primary["speed_profile"] if primary else None,
            "confidence": round(scored[0]["compatibility_score"], 3) if scored else 0.0,
            "execution_mode": execution_mode,
            "approval_required": self._approval_required(contract, execution_mode, risk_level),
            "risk_level": risk_level,
            "provider_scores": provider_scores,
            "routing_factors": self._routing_factors(contract),
            "timeline": timeline,
            "external_request_executed": False,
            "generated_at": utc_now(),
        }
        append_audit_event(
            "routing_completed",
            contract["requested_by"],
            {
                "capability_id": contract["capability_id"],
                "plan_id": plan["plan_id"],
                "primary_provider": primary["provider_id"] if primary else None,
                "confidence": plan["confidence"],
                "external_request_executed": False,
            },
            risk=risk_level.lower(),
        )
        if primary and primary.get("provider_role") in {"economic_primary", "economic_fallback"}:
            append_audit_event(
                "economic_provider_selected",
                contract["requested_by"],
                {
                    "capability_id": contract["capability_id"],
                    "plan_id": plan["plan_id"],
                    "provider_id": primary["provider_id"],
                    "execution_mode": execution_mode,
                },
                risk="low",
            )
        if execution_mode == "low_cost":
            append_audit_event(
                "low_cost_execution_mode",
                contract["requested_by"],
                {"capability_id": contract["capability_id"], "plan_id": plan["plan_id"], "external_request_executed": False},
                risk="low",
            )
        append_audit_event(
            "fallback_prepared",
            contract["requested_by"],
            {
                "capability_id": contract["capability_id"],
                "plan_id": plan["plan_id"],
                "fallback_chain": [provider["provider_id"] for provider in fallback_tree],
                "fallback_allowed": contract["fallback_allowed"],
            },
            risk=risk_level.lower(),
        )
        return plan

    def _profiles_with_overrides(self, disabled_provider_ids: list[str]) -> list[dict]:
        disabled = set(disabled_provider_ids)
        profiles = provider_abstraction_service.profiles()
        for profile in profiles:
            if profile["provider_id"] in disabled:
                profile["enabled"] = False
                profile["availability_status"] = "disabled_by_routing_input"
        return [annotate_provider(profile, profiles) for profile in profiles]

    def _evaluate_provider(self, profile: dict, contract: dict, execution_mode: str) -> dict:
        compatible, reason = self._compatibility(profile, contract)
        if not compatible:
            return self._score_record(profile, 0.0, 0.0, 0.0, 0.0, 0.0, reason, False)
        quality_score = self._quality_score(profile, contract)
        cost_score = self._cost_score(profile["cost_profile"], contract["cost_priority"])
        speed_score = self._speed_score(profile["speed_profile"], contract["speed_priority"])
        context_score = 1.0
        specialization_score = self._specialization_score(profile, contract)
        weights = self._weights(execution_mode)
        compatibility_score = (
            quality_score * weights["quality"]
            + cost_score * weights["cost"]
            + speed_score * weights["speed"]
            + context_score * weights["context"]
            + specialization_score * weights["specialization"]
        )
        return self._score_record(
            profile,
            quality_score,
            cost_score,
            speed_score,
            min(1.0, round(compatibility_score, 3)),
            specialization_score,
            self._score_reason(profile, contract, specialization_score),
            True,
        )

    def _compatibility(self, profile: dict, contract: dict) -> tuple[bool, str]:
        if not profile["enabled"]:
            return False, "provider_disabled"
        if profile["availability_status"].startswith("disabled"):
            return False, profile["availability_status"]
        if contract["capability_type"] not in profile["supported_capabilities"]:
            return False, "capability_not_supported"
        if profile["context_capacity"] < contract["context_size"]:
            return False, "context_capacity_too_small"
        constraints = {str(item).lower() for item in contract.get("provider_constraints", [])}
        active_constraints = constraints - NEUTRAL_CONSTRAINTS
        if active_constraints - CONSTRAINTS:
            return False, "unsupported_provider_constraint"
        if "local_only" in active_constraints and not profile["local_provider"]:
            return False, "local_only_constraint"
        if "premium_only" in active_constraints and not profile["premium_provider"]:
            return False, "premium_only_constraint"
        if "low_cost_only" in active_constraints and profile["cost_profile"] != "low_cost":
            return False, "low_cost_only_constraint"
        return True, "compatible"

    def _quality_score(self, profile: dict, contract: dict) -> float:
        reasoning_fit = min(QUALITY_VALUES[profile["reasoning_strength"]] / QUALITY_VALUES[contract["reasoning_level"]], 1.0)
        if contract["coding_level"] == "none":
            return reasoning_fit
        coding_fit = min(QUALITY_VALUES[profile["coding_strength"]] / QUALITY_VALUES[contract["coding_level"]], 1.0)
        if contract["capability_type"] in {"repair", "debugging", "coding", "frontend_generation", "backend_generation"}:
            return (reasoning_fit * 0.35) + (coding_fit * 0.65)
        return (reasoning_fit * 0.65) + (coding_fit * 0.35)

    def _cost_score(self, profile_cost: str, preferred_cost: str) -> float:
        if preferred_cost == "low_cost":
            return {"low_cost": 1.0, "balanced": 0.72, "premium_allowed": 0.38}[profile_cost]
        if preferred_cost == "premium_allowed":
            return {"premium_allowed": 1.0, "balanced": 0.86, "low_cost": 0.62}[profile_cost]
        return {"balanced": 1.0, "low_cost": 0.9, "premium_allowed": 0.68}[profile_cost]

    def _speed_score(self, profile_speed: str, preferred_speed: str) -> float:
        if preferred_speed == "fast":
            return {"fast": 1.0, "balanced": 0.78, "maximum_quality": 0.48}[profile_speed]
        if preferred_speed == "maximum_quality":
            return {"maximum_quality": 1.0, "balanced": 0.86, "fast": 0.58}[profile_speed]
        return {"balanced": 1.0, "fast": 0.86, "maximum_quality": 0.78}[profile_speed]

    def _specialization_score(self, profile: dict, contract: dict) -> float:
        score = 0.7
        capability_type = contract["capability_type"]
        simple_fast = contract["reasoning_level"] == "low" and contract["coding_level"] == "none" and contract["speed_priority"] == "fast" and contract["context_size"] <= 32000
        if capability_type in {"coding", "frontend_generation", "backend_generation", "debugging", "repair"} and profile["coding_strength"] in {"high", "expert"}:
            score += 0.15
        if capability_type in {"reasoning", "architecture", "analysis", "repair"} and profile["reasoning_strength"] in {"high", "extreme"}:
            score += 0.15
        if capability_type == "repair" and profile["premium_provider"]:
            score += 0.1
        if simple_fast and profile["local_provider"]:
            score += 0.18
        if contract["cost_priority"] == "low_cost" and profile["cost_profile"] == "low_cost":
            score += 0.08
        if profile.get("provider_role") in {"economic_primary", "economic_fallback"} and contract["capability_type"] in {
            "analysis",
            "summarization",
            "documentation",
            "coding",
            "frontend_generation",
            "backend_generation",
            "debugging",
        }:
            score += 0.08
        return min(1.0, score)

    def _weights(self, execution_mode: str) -> dict[str, float]:
        if execution_mode == "low_cost":
            return {"quality": 0.24, "cost": 0.34, "speed": 0.16, "context": 0.08, "specialization": 0.18}
        if execution_mode == "premium":
            return {"quality": 0.38, "cost": 0.06, "speed": 0.14, "context": 0.14, "specialization": 0.28}
        if execution_mode == "safe_mode":
            return {"quality": 0.2, "cost": 0.2, "speed": 0.22, "context": 0.1, "specialization": 0.28}
        if execution_mode == "experimental":
            return {"quality": 0.28, "cost": 0.1, "speed": 0.22, "context": 0.14, "specialization": 0.26}
        return {"quality": 0.3, "cost": 0.2, "speed": 0.2, "context": 0.12, "specialization": 0.18}

    def _score_record(
        self,
        profile: dict,
        quality_score: float,
        cost_score: float,
        speed_score: float,
        compatibility_score: float,
        specialization_score: float,
        reason: str,
        compatible: bool,
    ) -> dict:
        return {
            "provider_id": profile["provider_id"],
            "provider_name": profile["provider_name"],
            "quality_score": round(quality_score, 3),
            "cost_score": round(cost_score, 3),
            "speed_score": round(speed_score, 3),
            "compatibility_score": round(compatibility_score, 3),
            "reason": reason,
            "specialization_score": round(specialization_score, 3),
            "compatible": compatible,
            "fallback_priority": profile["fallback_priority"],
            "profile": profile,
        }

    def _score_reason(self, profile: dict, contract: dict, specialization_score: float) -> str:
        return (
            f"{profile['provider_id']} matches {contract['capability_type']} through "
            f"reasoning={profile['reasoning_strength']}, coding={profile['coding_strength']}, "
            f"cost={profile['cost_profile']}, speed={profile['speed_profile']}, "
            f"specialization={round(specialization_score, 2)}."
        )

    def _execution_mode(self, contract: dict) -> str:
        constraints = {str(item).lower() for item in contract.get("provider_constraints", [])}
        if "experimental_mode" in constraints:
            return "experimental"
        if "safe_mode" in constraints or "local_only" in constraints:
            return "safe_mode"
        if contract["cost_priority"] == "low_cost":
            return "low_cost"
        if contract["cost_priority"] == "premium_allowed" or contract["capability_type"] == "repair" or contract["reasoning_level"] == "extreme":
            return "premium"
        return "low_cost"

    def _risk_level(self, contract: dict, execution_mode: str) -> str:
        if contract["capability_type"] == "repair" or contract["reasoning_level"] == "extreme" or execution_mode == "experimental":
            return "HIGH"
        if contract["requires_human_approval"] or execution_mode == "premium":
            return "MEDIUM"
        return "LOW"

    def _approval_required(self, contract: dict, execution_mode: str, risk_level: str) -> bool:
        return bool(contract["requires_human_approval"] or risk_level in {"MEDIUM", "HIGH"} or execution_mode in {"premium", "experimental"})

    def _routing_factors(self, contract: dict) -> dict[str, str | int | bool]:
        return {
            "reasoning_level": contract["reasoning_level"],
            "coding_complexity": contract["coding_level"],
            "cost_priority": contract["cost_priority"],
            "speed_priority": contract["speed_priority"],
            "context_size": contract["context_size"],
            "fallback_allowed": contract["fallback_allowed"],
            "capability_type": contract["capability_type"],
            "economic_provider_priority": " -> ".join(economic_provider_ids()) or "none",
        }

    def _routing_reason(self, contract: dict, primary: dict | None, fallback_tree: list[dict], execution_mode: str) -> str:
        if not primary:
            return "No provider profile satisfies capability, constraints, enabled status, and context requirements."
        fallback = f" Fallback chain prepared: {', '.join(provider['provider_id'] for provider in fallback_tree)}." if fallback_tree else " Fallback chain is empty."
        return f"{primary['provider_id']} selected for {contract['capability_type']} in {execution_mode} mode after provider profile scoring.{fallback}"

    def _selected_detail(self, primary: dict | None) -> str:
        if not primary:
            return "No compatible provider selected."
        return f"{primary['provider_id']} selected as primary provider profile."

    def _selection_key(self, item: dict, execution_mode: str) -> tuple:
        profile = item["profile"]
        if execution_mode == "premium":
            premium_bias = 0 if profile["premium_provider"] else 1
            return (premium_bias, -item["compatibility_score"], profile["fallback_priority"], profile["provider_id"])
        return (-item["compatibility_score"], operational_priority(profile), profile["provider_id"])

    def _fallback_detail(self, contract: dict, fallback_tree: list[dict]) -> str:
        if not contract["fallback_allowed"]:
            return "Fallback disabled by CapabilityContract."
        if not fallback_tree:
            return "No compatible fallback providers available."
        return f"Fallback tree prepared: {' -> '.join(provider['provider_id'] for provider in fallback_tree)}."

    def _event(self, event: str, detail: str) -> dict:
        return {"timestamp": utc_now(), "event": event, "detail": detail}


capability_routing_engine = CapabilityRoutingEngine()
