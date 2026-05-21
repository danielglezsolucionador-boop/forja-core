from __future__ import annotations


class ProviderService:
    def list_providers(self) -> list[dict]:
        return [
            {
                "id": "ai.local-disabled",
                "kind": "ai",
                "status": "disabled",
                "reason": "external provider execution is not enabled in local FORJA",
                "timeout_ms": 30000,
                "retry_limit": 0,
            },
            {
                "id": "notification.local-queue",
                "kind": "notification",
                "status": "available",
                "reason": "local queue only; no external delivery",
                "timeout_ms": 5000,
                "retry_limit": 0,
            },
        ]


provider_service = ProviderService()
