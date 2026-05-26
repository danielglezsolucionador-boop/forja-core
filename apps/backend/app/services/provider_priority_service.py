from __future__ import annotations

import os
from typing import Iterable

from app.services.provider_abstraction_service import MOCK_PROVIDER_PROFILES


ECONOMIC_PROVIDER_ENV = "FORJA_ECONOMIC_PROVIDER_ID"


def provider_profiles() -> list[dict]:
    return [dict(profile) for profile in MOCK_PROVIDER_PROFILES]


def economic_provider_ids(profiles: Iterable[dict] | None = None) -> list[str]:
    records = list(profiles or provider_profiles())
    configured = os.environ.get(ECONOMIC_PROVIDER_ENV, "").strip().lower()
    low_cost = [
        profile["provider_id"]
        for profile in sorted(records, key=lambda item: (item["fallback_priority"], item["provider_id"]))
        if profile["cost_profile"] == "low_cost" and not profile["local_provider"] and profile["enabled"]
    ]
    if configured and configured in low_cost:
        return [configured, *[provider_id for provider_id in low_cost if provider_id != configured]]
    return low_cost


def premium_provider_ids(profiles: Iterable[dict] | None = None) -> list[str]:
    records = list(profiles or provider_profiles())
    return [
        profile["provider_id"]
        for profile in sorted(records, key=lambda item: (item["fallback_priority"], item["provider_id"]))
        if profile["premium_provider"] and profile["enabled"]
    ]


def real_execution_provider_ids(profiles: Iterable[dict] | None = None) -> list[str]:
    records = list(profiles or provider_profiles())
    economic = economic_provider_ids(records)
    premium = premium_provider_ids(records)
    return [*economic, *[provider_id for provider_id in premium if provider_id not in economic]]


def provider_role(profile: dict, profiles: Iterable[dict] | None = None) -> str:
    records = list(profiles or provider_profiles())
    economic = economic_provider_ids(records)
    if economic and profile["provider_id"] == economic[0]:
        return "economic_primary"
    if profile["provider_id"] in economic:
        return "economic_fallback"
    if profile.get("premium_provider"):
        return "premium_future"
    if profile.get("local_provider"):
        return "local_safe"
    return "balanced_future"


def operational_priority(profile: dict, profiles: Iterable[dict] | None = None) -> int:
    role = provider_role(profile, profiles)
    role_weight = {
        "economic_primary": 10,
        "economic_fallback": 20,
        "local_safe": 35,
        "balanced_future": 45,
        "premium_future": 80,
    }[role]
    return role_weight + int(profile.get("fallback_priority", 99))


def annotate_provider(profile: dict, profiles: Iterable[dict] | None = None) -> dict:
    annotated = dict(profile)
    annotated["provider_role"] = provider_role(annotated, profiles)
    annotated["operational_priority"] = operational_priority(annotated, profiles)
    return annotated
