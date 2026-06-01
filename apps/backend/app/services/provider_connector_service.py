from __future__ import annotations

from abc import ABC, abstractmethod
import os

from app.core.audit import append_audit_event, utc_now
from app.core.storage import JsonStore, store
from app.services.provider_abstraction_service import MOCK_PROVIDER_PROFILES


PROVIDER_ENV_VARS = {
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "qwen": "QWEN_API_KEY",
}
PROVIDER_ENV_ALIASES = {
    "openrouter": ("FORJA_OPENROUTER_API_KEY",),
    "qwen": ("QWEN_API_KEY", "DASHSCOPE_API_KEY"),
}
PROVIDER_CREDENTIAL_PATTERNS = {
    "openrouter": {"prefixes": ("sk-or-",), "min_length": 18},
    "openai": {"prefixes": ("sk-",), "min_length": 18},
    "anthropic": {"prefixes": ("sk-ant-",), "min_length": 18},
    "gemini": {"prefixes": ("AIza",), "min_length": 18},
    "deepseek": {"prefixes": ("sk-",), "min_length": 18},
    "qwen": {"prefixes": ("sk-",), "min_length": 18},
}
READY_STATES = {"ready", "configured"}


class ProviderConnectorError(ValueError):
    pass


class ProviderConnectorInterface(ABC):
    @abstractmethod
    def initialize(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def validate(self, capability_type: str | None = None) -> dict:
        raise NotImplementedError

    @abstractmethod
    def supports_capability(self, capability_type: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_provider_status(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def get_health_snapshot(self) -> dict:
        raise NotImplementedError


class BaseProviderConnector(ProviderConnectorInterface):
    def __init__(self, profile: dict, enabled: bool) -> None:
        self.profile = profile
        self.provider_id = profile["provider_id"]
        self.enabled = enabled
        self.env_var = PROVIDER_ENV_VARS.get(self.provider_id)
        self.credential_required = self.env_var is not None

    def initialize(self) -> dict:
        return self.get_provider_status()

    def validate(self, capability_type: str | None = None) -> dict:
        status = self.get_provider_status()
        compatible = True
        reason = status["status_reason"]
        if capability_type and not self.supports_capability(capability_type):
            compatible = False
            reason = "capability_not_supported"
        elif status["connector_state"] not in READY_STATES:
            compatible = False
        return {
            "provider_id": self.provider_id,
            "capability_type": capability_type,
            "compatible": compatible,
            "connector_state": status["connector_state"],
            "credential_state": status["credential_state"],
            "reason": reason,
        }

    def supports_capability(self, capability_type: str) -> bool:
        return capability_type in self.profile["supported_capabilities"]

    def get_provider_status(self) -> dict:
        credential_state, reason = self._credential_state()
        connector_state = self._connector_state(credential_state)
        safe_initialization = connector_state in READY_STATES
        return {
            "provider_id": self.provider_id,
            "provider_name": self.profile["provider_name"],
            "connector_state": connector_state,
            "credential_state": credential_state,
            "credential_configured": credential_state in {"configured", "not_required"},
            "credential_required": self.credential_required,
            "credential_env_var": self.env_var,
            "enabled": self.enabled,
            "safe_initialization": safe_initialization,
            "supports_real_connection": self.credential_required,
            "local_provider": self.profile["local_provider"],
            "supported_capabilities": self.profile["supported_capabilities"],
            "reasoning_strength": self.profile["reasoning_strength"],
            "coding_strength": self.profile["coding_strength"],
            "cost_profile": self.profile["cost_profile"],
            "speed_profile": self.profile["speed_profile"],
            "fallback_priority": self.profile["fallback_priority"],
            "compatibility_ready": safe_initialization,
            "status_reason": reason,
            "health": self.get_health_snapshot(),
            "secrets_exposed": False,
        }

    def get_health_snapshot(self) -> dict:
        connector_state = self._connector_state(self._credential_state()[0])
        return {
            "provider_id": self.provider_id,
            "connector_state": connector_state,
            "credential_state": self._credential_state()[0],
            "simulated_latency": self._simulated_latency(connector_state),
            "simulated_failure_rate": self._simulated_failure_rate(connector_state),
            "last_checked": utc_now(),
        }

    def _credential_state(self) -> tuple[str, str]:
        if not self.enabled:
            return "missing" if self.credential_required else "not_required", "connector_disabled"
        if not self.credential_required:
            return "not_required", "local_connector_prepared"
        value = os.environ.get(str(self.env_var), "")
        if not value:
            value = self._credential_alias_value()
        if not value:
            return "missing", "missing_credentials_detected"
        if not self._valid_credential_format(value):
            return "invalid", "invalid_credential_format"
        return "configured", "credential_format_validated"

    def _connector_state(self, credential_state: str) -> str:
        if not self.enabled:
            return "disabled"
        if credential_state == "not_required":
            return "ready"
        if credential_state == "configured":
            return "ready"
        if credential_state == "invalid":
            return "invalid_credentials"
        if credential_state == "missing":
            return "missing_credentials"
        return "unavailable"

    def _valid_credential_format(self, value: str) -> bool:
        pattern = PROVIDER_CREDENTIAL_PATTERNS.get(self.provider_id)
        if not pattern:
            return True
        stripped = value.strip()
        return len(stripped) >= pattern["min_length"] and any(stripped.startswith(prefix) for prefix in pattern["prefixes"])

    def _credential_alias_value(self) -> str:
        for env_var in PROVIDER_ENV_ALIASES.get(self.provider_id, ()):
            value = os.environ.get(env_var, "").strip()
            if value:
                return value
        return ""

    def _simulated_latency(self, connector_state: str) -> int:
        if connector_state == "ready":
            if self.profile["local_provider"]:
                return 85
            if self.profile["speed_profile"] == "fast":
                return 240
            if self.profile["speed_profile"] == "balanced":
                return 420
            return 760
        if connector_state == "disabled":
            return 0
        return 2000

    def _simulated_failure_rate(self, connector_state: str) -> float:
        if connector_state == "ready":
            return 0.02 if self.profile["premium_provider"] else 0.05
        if connector_state == "disabled":
            return 1.0
        return 1.0


class LocalModelConnector(BaseProviderConnector):
    def _credential_state(self) -> tuple[str, str]:
        if not self.enabled:
            return "not_required", "connector_disabled"
        return "not_required", "local_llm_connector_prepared_without_model_execution"


class OpenRouterProviderConnector(BaseProviderConnector):
    pass


class ProviderConnectorLayer:
    def __init__(self, state_store: JsonStore | None = None) -> None:
        self._store = state_store or store("provider_connectors")

    def snapshot(self) -> dict:
        payload = self._ensure_initialized()
        providers = self._records(payload)
        configured = [provider["provider_id"] for provider in providers if provider["credential_configured"]]
        missing = [provider["provider_id"] for provider in providers if provider["credential_state"] == "missing"]
        ready = [provider["provider_id"] for provider in providers if provider["connector_state"] == "ready"]
        fallback_ready = len(ready) >= 2 or "local_llm" in ready
        return {
            "connector_layer_status": "ready" if ready else "attention_required",
            "providers": providers,
            "configured_provider_ids": configured,
            "missing_provider_ids": missing,
            "ready_provider_ids": ready,
            "fallback_ready": fallback_ready,
            "timeline": payload.get("timeline", [])[-12:],
            "external_request_executed": False,
            "generated_at": utc_now(),
        }

    def validate(self, payload: dict) -> dict:
        state = self._ensure_initialized()
        provider_id = payload["provider_id"]
        capability_type = payload["capability_type"]
        connector = self._connector(provider_id, state)
        validation = connector.validate(capability_type)
        records = self._records(state)
        fallback_provider_ids = [
            record["provider_id"]
            for record in records
            if record["provider_id"] != provider_id and record["connector_state"] == "ready" and capability_type in record["supported_capabilities"]
        ]
        compatible = bool(validation["compatible"])
        reason = validation["reason"]
        append_audit_event(
            "provider_ready" if compatible else "provider_validation_failed",
            "system",
            {
                "provider_id": provider_id,
                "capability_type": capability_type,
                "compatible": compatible,
                "reason": reason,
                "external_request_executed": False,
            },
            risk="low" if compatible else "medium",
        )
        return {
            "provider_id": provider_id,
            "capability_type": capability_type,
            "compatible": compatible,
            "connector_state": validation["connector_state"],
            "credential_state": validation["credential_state"],
            "fallback_provider_ids": fallback_provider_ids,
            "reason": reason,
            "external_request_executed": False,
            "generated_at": utc_now(),
        }

    def disable_provider(self, provider_id: str) -> dict:
        return self._set_enabled(provider_id, False, "connector_disabled")

    def enable_provider(self, provider_id: str) -> dict:
        return self._set_enabled(provider_id, True, "provider_connector_loaded")

    def _ensure_initialized(self) -> dict:
        def mutator(payload: dict) -> None:
            payload.setdefault("providers", {})
            payload.setdefault("timeline", [])
            initialized = bool(payload.get("initialized"))
            if not initialized:
                payload["timeline"].append(self._event("connector.initialized", "ProviderConnectorLayer initialized in safe validation mode."))
            for profile in MOCK_PROVIDER_PROFILES:
                provider_id = profile["provider_id"]
                if provider_id not in payload["providers"]:
                    payload["providers"][provider_id] = {"enabled": True}
                    append_audit_event(
                        "provider_connector_loaded",
                        "system",
                        {"provider_id": provider_id, "external_request_executed": False, "secrets_exposed": False},
                        risk="low",
                    )
            if not initialized:
                payload["timeline"].append(self._event("provider.validated", "Provider connector registry loaded for safe credential checks."))
                payload["timeline"].append(self._event("fallback.prepared", "Fallback readiness prepared from ready connectors only."))
                payload["initialized"] = True
            payload["timeline"] = payload["timeline"][-24:]

        self._store.update({"providers": {}, "timeline": []}, mutator)
        return self._store.read({"providers": {}, "timeline": []})

    def _records(self, payload: dict) -> list[dict]:
        records = []
        for profile in sorted(MOCK_PROVIDER_PROFILES, key=lambda item: item["fallback_priority"]):
            connector = self._connector(profile["provider_id"], payload)
            record = connector.initialize()
            self._audit_state(record)
            records.append(record)
        return records

    def _connector(self, provider_id: str, payload: dict) -> BaseProviderConnector:
        profile = next((item for item in MOCK_PROVIDER_PROFILES if item["provider_id"] == provider_id), None)
        if not profile:
            raise ProviderConnectorError("provider_connector_not_registered")
        enabled = bool(payload.get("providers", {}).get(provider_id, {}).get("enabled", True))
        if provider_id == "local_llm":
            return LocalModelConnector(profile, enabled)
        if provider_id == "openrouter":
            return OpenRouterProviderConnector(profile, enabled)
        return BaseProviderConnector(profile, enabled)

    def _set_enabled(self, provider_id: str, enabled: bool, audit_event: str) -> dict:
        def mutator(payload: dict) -> None:
            payload.setdefault("providers", {})
            if provider_id not in payload["providers"]:
                if not any(profile["provider_id"] == provider_id for profile in MOCK_PROVIDER_PROFILES):
                    raise ProviderConnectorError("provider_connector_not_registered")
                payload["providers"][provider_id] = {}
            payload["providers"][provider_id]["enabled"] = enabled
            payload.setdefault("timeline", []).append(
                self._event("provider.ready" if enabled else "provider.disabled", f"{provider_id} connector {'enabled' if enabled else 'disabled'}.")
            )
            payload["timeline"] = payload["timeline"][-24:]
            append_audit_event(
                audit_event,
                "system",
                {"provider_id": provider_id, "enabled": enabled, "external_request_executed": False, "secrets_exposed": False},
                risk="low" if enabled else "medium",
            )

        self._store.update({"providers": {}, "timeline": []}, mutator)
        return self.snapshot()

    def _audit_state(self, record: dict) -> None:
        if record["connector_state"] == "ready":
            append_audit_event(
                "provider_ready",
                "system",
                {"provider_id": record["provider_id"], "credential_state": record["credential_state"], "external_request_executed": False},
                risk="low",
            )
        elif record["connector_state"] == "missing_credentials":
            append_audit_event(
                "missing_credentials_detected",
                "system",
                {"provider_id": record["provider_id"], "credential_env_var": record["credential_env_var"], "external_request_executed": False},
                risk="medium",
            )
        elif record["connector_state"] == "invalid_credentials":
            append_audit_event(
                "provider_validation_failed",
                "system",
                {"provider_id": record["provider_id"], "reason": "invalid_credential_format", "external_request_executed": False},
                risk="medium",
            )
        elif record["connector_state"] == "disabled":
            append_audit_event(
                "connector_disabled",
                "system",
                {"provider_id": record["provider_id"], "external_request_executed": False},
                risk="medium",
            )

    def _event(self, event: str, detail: str) -> dict:
        return {"timestamp": utc_now(), "event": event, "detail": detail}


provider_connector_layer = ProviderConnectorLayer()
