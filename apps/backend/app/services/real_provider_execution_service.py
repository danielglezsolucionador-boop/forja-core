from __future__ import annotations

import json
import os
from pathlib import Path
import re
import time
import uuid

import httpx

from app.core.audit import append_audit_event, read_audit_events, utc_now
from app.core.config import settings
from app.core.storage import JsonStore, store
from app.services.provider_connector_service import ProviderConnectorLayer, provider_connector_layer
from app.services.provider_priority_service import economic_provider_ids, operational_priority, premium_provider_ids, real_execution_provider_ids


PREMIUM_REAL_PROVIDERS = {"openai", "anthropic"}
ALLOWED_REAL_CAPABILITIES = {"reasoning", "analysis", "summarization", "architecture", "documentation"}
TASK_OUTPUTS = {
    "readme": ("generated_readme", "Generated README", "README.generated.md"),
    "summary": ("generated_summary", "Generated summary", "summary.generated.md"),
    "architecture_notes": ("architecture_notes", "Architecture notes", "architecture-notes.generated.md"),
    "documentation": ("technical_documentation", "Technical documentation", "documentation.generated.md"),
}
TASK_CAPABILITIES = {
    "readme": {"documentation", "architecture", "analysis"},
    "summary": {"summarization", "analysis", "reasoning", "documentation"},
    "architecture_notes": {"architecture", "analysis", "documentation"},
    "documentation": {"documentation", "architecture", "analysis"},
}
MAX_REQUEST_CHARS = 1800
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 3
SAFE_MODE_BLOCKLIST = {
    "../",
    "api key",
    "cmd.exe",
    "complete application",
    "delete files",
    "deploy",
    "exfiltrate",
    "full app",
    "generate all files",
    "infinite loop",
    "npm install",
    "overwrite",
    "pip install",
    "powershell",
    "rm -rf",
    "secret",
    "shell",
    "token",
    "while true",
}
PROVIDER_COST_RATE = {"openrouter": 0.00065, "deepseek": 0.00014, "qwen": 0.00018, "openai": 0.0006, "anthropic": 0.003}
WORKSPACE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,79}$")


class RealProviderTransportError(RuntimeError):
    def __init__(self, reason: str, failure_mode: str = "provider_failure_detected") -> None:
        super().__init__(reason)
        self.reason = reason
        self.failure_mode = failure_mode


class HTTPRealProviderTransport:
    def execute(self, provider_id: str, prompt: str, max_tokens: int, timeout_seconds: int) -> dict:
        if provider_id == "openrouter":
            return self._execute_openrouter(prompt, max_tokens, timeout_seconds)
        if provider_id in {"deepseek", "qwen"}:
            return self._execute_openai_compatible(provider_id, prompt, max_tokens, timeout_seconds)
        if provider_id == "openai":
            return self._execute_openai(prompt, max_tokens, timeout_seconds)
        if provider_id == "anthropic":
            return self._execute_anthropic(prompt, max_tokens, timeout_seconds)
        raise RealProviderTransportError("invalid_real_provider")

    def _execute_openrouter(self, prompt: str, max_tokens: int, timeout_seconds: int) -> dict:
        return self._execute_openai_compatible("openrouter", prompt, max_tokens, timeout_seconds)

    def _execute_openai_compatible(self, provider_id: str, prompt: str, max_tokens: int, timeout_seconds: int) -> dict:
        config = self._openai_compatible_config(provider_id)
        api_key = config["api_key"]
        if not api_key:
            raise RealProviderTransportError(f"missing_{provider_id}_credentials", "missing_credentials")
        payload = {
            "model": config["model"],
            "messages": [
                {"role": "system", "content": "You are FORJA running a small governed low-cost execution."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "stream": False,
        }
        try:
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            headers.update(config.get("headers", {}))
            response = httpx.post(
                f"{config['base_url'].rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise RealProviderTransportError("provider_timeout", "timeout") from exc
        except httpx.HTTPError as exc:
            raise RealProviderTransportError("provider_http_error", "provider_failure_detected") from exc
        data = response.json()
        text = ""
        choices = data.get("choices") or []
        if choices:
            message = choices[0].get("message", {})
            text = str(message.get("content", "")).strip()
        return {"text": text, "model": data.get("model", config["model"]), "usage": data.get("usage", {})}

    def _openai_compatible_config(self, provider_id: str) -> dict:
        if provider_id == "deepseek":
            return {
                "api_key": os.environ.get("DEEPSEEK_API_KEY", "").strip(),
                "base_url": os.environ.get("FORJA_DEEPSEEK_BASE_URL", os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com")),
                "model": os.environ.get("FORJA_DEEPSEEK_MODEL", os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")),
            }
        if provider_id == "openrouter":
            return {
                "api_key": os.environ.get("OPENROUTER_API_KEY", "").strip(),
                "base_url": os.environ.get("FORJA_OPENROUTER_BASE_URL", os.environ.get("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")),
                "model": os.environ.get("FORJA_OPENROUTER_MODEL", os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-chat")),
                "headers": {
                    "HTTP-Referer": os.environ.get("FORJA_PUBLIC_URL", "https://forja-frontend.onrender.com"),
                    "X-OpenRouter-Title": "FORJA Operational Core",
                },
            }
        if provider_id == "qwen":
            return {
                "api_key": os.environ.get("QWEN_API_KEY", os.environ.get("DASHSCOPE_API_KEY", "")).strip(),
                "base_url": os.environ.get(
                    "FORJA_QWEN_BASE_URL",
                    os.environ.get("QWEN_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
                ),
                "model": os.environ.get("FORJA_QWEN_MODEL", os.environ.get("QWEN_MODEL", "qwen-plus")),
            }
        raise RealProviderTransportError("invalid_openai_compatible_provider")

    def _execute_openai(self, prompt: str, max_tokens: int, timeout_seconds: int) -> dict:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RealProviderTransportError("missing_openai_credentials", "missing_credentials")
        model = os.environ.get("FORJA_OPENAI_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
        payload = {
            "model": model,
            "input": prompt,
            "max_output_tokens": max_tokens,
            "store": False,
            "metadata": {"forja_scope": "first_real_ai_execution"},
        }
        try:
            response = httpx.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise RealProviderTransportError("provider_timeout", "timeout") from exc
        except httpx.HTTPError as exc:
            raise RealProviderTransportError("provider_http_error", "provider_failure_detected") from exc
        data = response.json()
        return {
            "text": self._openai_text(data),
            "model": data.get("model", model),
            "usage": data.get("usage", {}),
        }

    def _execute_anthropic(self, prompt: str, max_tokens: int, timeout_seconds: int) -> dict:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise RealProviderTransportError("missing_anthropic_credentials", "missing_credentials")
        model = os.environ.get("FORJA_ANTHROPIC_MODEL", os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"))
        payload = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}
        try:
            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise RealProviderTransportError("provider_timeout", "timeout") from exc
        except httpx.HTTPError as exc:
            raise RealProviderTransportError("provider_http_error", "provider_failure_detected") from exc
        data = response.json()
        text_parts = [item.get("text", "") for item in data.get("content", []) if item.get("type") == "text"]
        return {"text": "\n".join(part for part in text_parts if part).strip(), "model": data.get("model", model), "usage": data.get("usage", {})}

    def _openai_text(self, data: dict) -> str:
        if isinstance(data.get("output_text"), str):
            return data["output_text"].strip()
        parts: list[str] = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if content.get("type") == "output_text" and isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()


class RealProviderExecutionEngine:
    def __init__(
        self,
        state_store: JsonStore | None = None,
        connector_layer: ProviderConnectorLayer | None = None,
        transport: HTTPRealProviderTransport | None = None,
        workspace_base_dir: Path | None = None,
    ) -> None:
        self._store = state_store or store("real_provider_executions")
        self._connector_layer = connector_layer or provider_connector_layer
        self._transport = transport or HTTPRealProviderTransport()
        self._workspace_base_dir = Path(workspace_base_dir) if workspace_base_dir else settings.base_dir

    def execute(self, payload: dict) -> dict:
        execution_id = f"real-ai-{uuid.uuid4()}"
        requested_by = payload.get("requested_by", "ceo")
        capability_type = payload.get("capability_type", "documentation")
        task_type = payload.get("task_type", "summary")
        max_tokens = int(payload.get("max_tokens", 300))
        timeout_seconds = int(payload.get("timeout_seconds", 20))
        safe_mode = bool(payload.get("safe_mode", True))
        fallback_allowed = bool(payload.get("fallback_allowed", True))
        objective = str(payload.get("objective", "")).strip()
        timeline = [self._event("provider.selected", "Real provider selection started under governed safe mode.")]

        append_audit_event(
            "real_provider_execution_started",
            requested_by,
            {
                "execution_id": execution_id,
                "capability_type": capability_type,
                "task_type": task_type,
                "safe_mode": safe_mode,
                "external_request_executed": False,
            },
            risk="medium",
        )

        blocking_reason = self._validate_request(payload)
        if blocking_reason:
            return self._failed_result(
                execution_id,
                payload,
                timeline,
                blocking_reason,
                "blocked",
                rate_limit_remaining=RATE_LIMIT_MAX_REQUESTS,
            )

        rate_limit_max_requests = int(payload.get("rate_limit_max_requests", RATE_LIMIT_MAX_REQUESTS))
        rate = self._check_rate_limit(requested_by, rate_limit_max_requests)
        if not rate["allowed"]:
            return self._failed_result(execution_id, payload, timeline, "rate_limit_exceeded", "blocked", rate["remaining"])

        selection = self._select_provider(payload)
        primary = selection["primary"]
        fallback = selection["fallback"]
        primary_attempted = selection["primary_attempted"]
        if selection["failure_reason"]:
            append_audit_event(
                "provider_failure_detected",
                requested_by,
                {
                    "execution_id": execution_id,
                    "provider_id": primary_attempted,
                    "reason": selection["failure_reason"],
                    "external_request_executed": False,
                },
                risk="medium",
            )
            timeline.append(self._event("provider.failure_detected", f"{primary_attempted or 'provider'} unavailable: {selection['failure_reason']}."))
            if fallback_allowed and fallback:
                append_audit_event(
                    "fallback_real_ai_triggered",
                    requested_by,
                    {
                        "execution_id": execution_id,
                        "primary_provider": primary_attempted,
                        "fallback_provider": fallback,
                    },
                    risk="medium",
                )
                timeline.append(self._event("fallback.triggered", f"Fallback real AI prepared with {fallback}."))
                primary = fallback
            else:
                return self._failed_result(execution_id, payload, timeline, selection["failure_reason"], "failed", rate["remaining"], primary_attempted)

        if not primary:
            return self._failed_result(execution_id, payload, timeline, "no_real_provider_ready", "failed", rate["remaining"], primary_attempted)

        prompt = self._build_prompt(task_type, objective, max_tokens)
        workspace_id = self._workspace_id(payload.get("workspace_id"), execution_id)
        started = time.perf_counter()
        timeline.append(self._event("provider.connected", f"{primary} connector validated without exposing credentials."))
        append_audit_event(
            "provider_connected",
            requested_by,
            {"execution_id": execution_id, "provider_id": primary, "credential_exposed": False},
            risk="medium",
        )
        if primary in economic_provider_ids():
            append_audit_event(
                "economic_provider_selected",
                requested_by,
                {"execution_id": execution_id, "provider_id": primary, "external_request_executed": False},
                risk="low",
            )
            append_audit_event(
                "low_cost_execution_mode",
                requested_by,
                {"execution_id": execution_id, "provider_id": primary, "max_tokens": max_tokens},
                risk="low",
            )
        attempt_chain = [primary]
        if fallback_allowed and fallback and fallback not in attempt_chain:
            attempt_chain.append(fallback)

        fallback_triggered = primary != selection["primary"] and selection["primary"] is not None
        provider_used: str | None = None
        model_used: str | None = None
        fallback_provider_used: str | None = primary if fallback_triggered else None
        external_request_executed = False
        generated_text = ""
        usage: dict = {}
        failure_reason = ""

        for attempt_index, provider_id in enumerate(attempt_chain):
            is_fallback_attempt = attempt_index > 0 or (fallback_triggered and provider_id == primary)
            timeline.append(self._event("request.executed", f"Small real AI request sent to {provider_id}."))
            try:
                response = self._transport.execute(provider_id, prompt, max_tokens, timeout_seconds)
                external_request_executed = True
                provider_used = provider_id
                model_used = str(response.get("model") or "").strip() or None
                fallback_provider_used = provider_id if is_fallback_attempt else fallback_provider_used
                generated_text = str(response.get("text", "")).strip()
                usage = response.get("usage", {}) if isinstance(response.get("usage", {}), dict) else {}
                if not generated_text:
                    raise RealProviderTransportError("empty_provider_response", "provider_failure_detected")
                timeline.append(self._event("response.received", f"Response received from {provider_id}."))
                break
            except RealProviderTransportError as exc:
                failure_reason = exc.reason
                append_audit_event(
                    "provider_failure_detected",
                    requested_by,
                    {
                        "execution_id": execution_id,
                        "provider_id": provider_id,
                        "reason": exc.reason,
                        "external_request_executed": external_request_executed,
                    },
                    risk="medium",
                )
                timeline.append(self._event("provider.failure_detected", f"{provider_id} failed: {exc.reason}."))
                remaining = attempt_chain[attempt_index + 1 :]
                if remaining:
                    fallback_triggered = True
                    fallback_provider_used = remaining[0]
                    append_audit_event(
                        "fallback_real_ai_triggered",
                        requested_by,
                        {"execution_id": execution_id, "primary_provider": provider_id, "fallback_provider": remaining[0]},
                        risk="medium",
                    )
                    timeline.append(self._event("fallback.triggered", f"Fallback real AI activated with {remaining[0]}."))
                    continue
                return self._failed_result(execution_id, payload, timeline, failure_reason, "failed", rate["remaining"], primary_attempted or provider_id)

        elapsed = round(time.perf_counter() - started, 2)
        estimated_tokens = self._estimated_tokens(prompt, generated_text, usage)
        estimated_cost = self._estimated_cost(provider_used, estimated_tokens)
        output = self._write_output(execution_id, workspace_id, task_type, generated_text, provider_used, model_used, estimated_tokens, estimated_cost)
        timeline.append(self._event("output.generated", f"{output['label']} saved inside the controlled workspace."))
        state = "completed" if not fallback_triggered else "degraded_mode"
        result = {
            "execution_id": execution_id,
            "provider_used": provider_used,
            "model_used": model_used,
            "primary_provider_attempted": primary_attempted or primary,
            "fallback_provider_used": fallback_provider_used,
            "capability_type": capability_type,
            "task_type": task_type,
            "execution_state": state,
            "execution_mode": "economic_low_cost" if provider_used in economic_provider_ids() else "low_cost_safe" if safe_mode else "controlled_real_ai",
            "estimated_tokens": estimated_tokens,
            "estimated_cost": estimated_cost,
            "estimated_duration": elapsed,
            "max_tokens": max_tokens,
            "max_execution_time": timeout_seconds,
            "max_request_size": MAX_REQUEST_CHARS,
            "response_received": True,
            "generated_text_preview": self._preview(generated_text),
            "outputs": [output],
            "fallback_triggered": fallback_triggered,
            "safe_mode": safe_mode,
            "rate_limit_remaining": rate["remaining"],
            "timeline": timeline,
            "audit_events": [],
            "external_request_executed": external_request_executed,
            "generated_at": utc_now(),
        }
        append_audit_event(
            "real_ai_execution_completed",
            requested_by,
            {
                "execution_id": execution_id,
                "provider_used": provider_used,
                "model_used": model_used,
                "task_type": task_type,
                "estimated_tokens": estimated_tokens,
                "estimated_cost": estimated_cost,
                "output_count": 1,
                "external_request_executed": external_request_executed,
            },
            risk="medium",
        )
        append_audit_event(
            "provider_execution_completed",
            requested_by,
            {
                "execution_id": execution_id,
                "provider_used": provider_used,
                "model_used": model_used,
                "execution_mode": result["execution_mode"],
                "estimated_cost": estimated_cost,
                "external_request_executed": external_request_executed,
            },
            risk="low" if provider_used in economic_provider_ids() else "medium",
        )
        return self._save_and_enrich(result)

    def latest(self) -> dict | None:
        records = self._records()
        return self._with_audit_preview(records[-1]) if records else None

    def status(self) -> dict:
        latest = self.latest()
        economic = economic_provider_ids()
        economic_provider_id = economic[0] if economic else None
        return {
            "engine_status": "ready",
            "safe_mode_default": True,
            "economic_provider_id": economic_provider_id,
            "economic_model": self._model_for_provider(economic_provider_id),
            "premium_fallback_provider_ids": premium_provider_ids(),
            "supported_real_providers": real_execution_provider_ids(),
            "supported_tasks": sorted(TASK_OUTPUTS),
            "max_tokens": 700,
            "max_execution_time": 45,
            "max_request_size": MAX_REQUEST_CHARS,
            "rate_limit": {"requests": RATE_LIMIT_MAX_REQUESTS, "window_seconds": RATE_LIMIT_WINDOW_SECONDS},
            "latest_execution": latest,
            "external_request_executed": bool(latest and latest.get("external_request_executed")),
            "generated_at": utc_now(),
        }

    def _validate_request(self, payload: dict) -> str | None:
        provider_id = self._clean_provider(payload.get("provider_id"))
        fallback_provider_id = self._clean_provider(payload.get("fallback_provider_id"))
        capability_type = payload.get("capability_type", "")
        task_type = payload.get("task_type", "")
        objective = str(payload.get("objective", "")).strip()
        workspace_id = payload.get("workspace_id")
        if provider_id and provider_id not in real_execution_provider_ids():
            return "invalid_provider"
        if fallback_provider_id and fallback_provider_id not in real_execution_provider_ids():
            return "invalid_fallback_provider"
        if workspace_id and (
            not WORKSPACE_ID_RE.match(str(workspace_id).strip())
            or ".." in str(workspace_id)
            or "/" in str(workspace_id)
            or "\\" in str(workspace_id)
        ):
            return "unsafe_workspace_id_blocked"
        if capability_type not in ALLOWED_REAL_CAPABILITIES:
            return "capability_not_allowed_for_first_real_execution"
        if task_type not in TASK_OUTPUTS:
            return "invalid_task_type"
        if capability_type not in TASK_CAPABILITIES[task_type]:
            return "capability_task_mismatch"
        if len(objective) > MAX_REQUEST_CHARS:
            return "max_request_size_exceeded"
        if not payload.get("allow_real_request", True):
            return "real_request_not_explicitly_allowed"
        if payload.get("safe_mode", True):
            normalized = " ".join(objective.lower().split())
            for blocked in SAFE_MODE_BLOCKLIST:
                if blocked in normalized:
                    return "safe_mode_blocked"
        return None

    def _check_rate_limit(self, actor: str, max_requests: int = RATE_LIMIT_MAX_REQUESTS) -> dict:
        now = time.time()

        def mutator(payload: dict) -> dict:
            buckets = payload.setdefault("rate_limits", {})
            records = buckets.setdefault(actor, [])
            records[:] = [float(item) for item in records if now - float(item) < RATE_LIMIT_WINDOW_SECONDS]
            if len(records) >= max_requests:
                return {"allowed": False, "remaining": 0}
            records.append(now)
            return {"allowed": True, "remaining": max_requests - len(records)}

        return self._store.update({"records": [], "rate_limits": {}}, mutator)

    def _select_provider(self, payload: dict) -> dict:
        requested = self._clean_provider(payload.get("provider_id"))
        fallback_requested = self._clean_provider(payload.get("fallback_provider_id"))
        capability_type = payload.get("capability_type", "")
        snapshot = self._connector_layer.snapshot()
        real_records = {
            provider["provider_id"]: provider
            for provider in snapshot["providers"]
            if provider["provider_id"] in real_execution_provider_ids()
        }
        ready = [
            provider_id
            for provider_id, record in sorted(real_records.items(), key=lambda item: operational_priority(item[1]))
            if record["connector_state"] == "ready" and capability_type in record["supported_capabilities"]
        ]

        economic = economic_provider_ids()
        primary_attempted = requested or (ready[0] if ready else economic[0] if economic else None)
        primary = None
        failure_reason = ""
        if requested:
            record = real_records.get(requested)
            if not record:
                failure_reason = "invalid_provider"
            elif record["connector_state"] != "ready":
                failure_reason = record["connector_state"]
            elif capability_type not in record["supported_capabilities"]:
                failure_reason = "capability_not_supported"
            else:
                primary = requested
        elif ready:
            primary = ready[0]
        else:
            attempted_record = real_records.get(primary_attempted or "")
            failure_reason = attempted_record["connector_state"] if attempted_record else "no_real_provider_ready"

        fallback = None
        fallback_candidates = [provider_id for provider_id in ready if provider_id != primary_attempted and provider_id != primary]
        if fallback_requested:
            record = real_records.get(fallback_requested)
            if record and record["connector_state"] == "ready" and capability_type in record["supported_capabilities"] and fallback_requested != primary:
                fallback = fallback_requested
        elif fallback_candidates:
            fallback = fallback_candidates[0]

        return {"primary": primary, "fallback": fallback, "primary_attempted": primary_attempted, "failure_reason": failure_reason}

    def _build_prompt(self, task_type: str, objective: str, max_tokens: int) -> str:
        task_label = {
            "readme": "Generate a concise README draft",
            "summary": "Generate a concise technical summary",
            "architecture_notes": "Generate short architecture notes",
            "documentation": "Generate a short technical documentation draft",
        }[task_type]
        return "\n".join(
            [
                "You are FORJA's first controlled real AI execution layer.",
                task_label + ".",
                "Write only the requested short operational artifact.",
                "Do not include secrets, API keys, shell commands, deployment steps, or full application generation.",
                f"Keep the answer under {max_tokens} output tokens.",
                f"Objective: {objective}",
            ]
        )

    def _write_output(
        self,
        execution_id: str,
        workspace_id: str,
        task_type: str,
        generated_text: str,
        provider_used: str | None,
        model_used: str | None,
        estimated_tokens: int,
        estimated_cost: float,
    ) -> dict:
        workspace_root = self._safe_workspace_root(workspace_id)
        outputs_dir = workspace_root / "outputs"
        audit_dir = workspace_root / "audit"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        audit_dir.mkdir(parents=True, exist_ok=True)
        kind, label, filename = TASK_OUTPUTS[task_type]
        target = (outputs_dir / f"{execution_id}-{filename}").resolve()
        self._ensure_inside(outputs_dir, target)
        if target.exists():
            raise RealProviderTransportError("output_overwrite_blocked")
        target.write_text(generated_text, encoding="utf-8")
        report = {
            "execution_id": execution_id,
            "provider_used": provider_used,
            "model_used": model_used,
            "task_type": task_type,
            "estimated_tokens": estimated_tokens,
            "estimated_cost": estimated_cost,
            "generated_at": utc_now(),
            "prompt_stored": False,
            "secrets_exposed": False,
        }
        (audit_dir / f"{execution_id}-execution-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        logical_path = f".forja/workspaces/{workspace_id}/outputs/{target.name}"
        return {
            "kind": kind,
            "label": label,
            "logical_path": logical_path,
            "status": "generated",
            "summary": self._preview(generated_text),
            "source": "real_provider_execution_engine",
        }

    def _safe_workspace_root(self, workspace_id: str) -> Path:
        if not WORKSPACE_ID_RE.match(workspace_id) or ".." in workspace_id or "/" in workspace_id or "\\" in workspace_id:
            raise RealProviderTransportError("unsafe_workspace_id_blocked")
        base = (self._workspace_base_dir / ".forja" / "workspaces").resolve()
        target = (base / workspace_id).resolve()
        self._ensure_inside(base, target)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _ensure_inside(self, base: Path, target: Path) -> None:
        resolved_base = base.resolve()
        resolved_target = target.resolve()
        if resolved_base != resolved_target and resolved_base not in resolved_target.parents:
            raise RealProviderTransportError("workspace_isolation_blocked")

    def _workspace_id(self, value: str | None, execution_id: str) -> str:
        if value:
            return value.strip()
        return f"real-ai-{execution_id.replace('real-ai-', '')[:12]}"

    def _estimated_tokens(self, prompt: str, generated_text: str, usage: dict) -> int:
        total_tokens = usage.get("total_tokens")
        if total_tokens is None and ("input_tokens" in usage or "output_tokens" in usage):
            total_tokens = int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
        if isinstance(total_tokens, int) and total_tokens > 0:
            return total_tokens
        return max(1, int((len(prompt) + len(generated_text)) / 4))

    def _estimated_cost(self, provider_used: str | None, estimated_tokens: int) -> float:
        rate = PROVIDER_COST_RATE.get(provider_used or "openai", 0.0006)
        return round((estimated_tokens / 1000) * rate, 6)

    def _model_for_provider(self, provider_id: str | None) -> str | None:
        if provider_id == "openrouter":
            return os.environ.get("FORJA_OPENROUTER_MODEL", os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-chat"))
        if provider_id == "deepseek":
            return os.environ.get("FORJA_DEEPSEEK_MODEL", os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"))
        if provider_id == "qwen":
            return os.environ.get("FORJA_QWEN_MODEL", os.environ.get("QWEN_MODEL", "qwen-plus"))
        if provider_id == "openai":
            return os.environ.get("FORJA_OPENAI_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
        if provider_id == "anthropic":
            return os.environ.get("FORJA_ANTHROPIC_MODEL", os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"))
        return None

    def _failed_result(
        self,
        execution_id: str,
        payload: dict,
        timeline: list[dict],
        reason: str,
        state: str,
        rate_limit_remaining: int,
        primary_attempted: str | None = None,
    ) -> dict:
        requested_by = payload.get("requested_by", "ceo")
        timeline.append(self._event("execution.failed", reason))
        result = {
            "execution_id": execution_id,
            "provider_used": None,
            "model_used": None,
            "primary_provider_attempted": primary_attempted or self._clean_provider(payload.get("provider_id")),
            "fallback_provider_used": None,
            "capability_type": payload.get("capability_type", "documentation"),
            "task_type": payload.get("task_type", "summary"),
            "execution_state": "failed",
            "execution_mode": self._execution_mode_for_payload(payload),
            "estimated_tokens": 0,
            "estimated_cost": 0.0,
            "estimated_duration": 0.0,
            "max_tokens": int(payload.get("max_tokens", 300)),
            "max_execution_time": int(payload.get("timeout_seconds", 20)),
            "max_request_size": MAX_REQUEST_CHARS,
            "response_received": False,
            "generated_text_preview": reason,
            "outputs": [
                {
                    "kind": "failure_report",
                    "label": "Real AI execution blocked",
                    "logical_path": None,
                    "status": "blocked" if state == "blocked" else "failed",
                    "summary": reason,
                    "source": "real_provider_execution_engine",
                }
            ],
            "fallback_triggered": False,
            "safe_mode": bool(payload.get("safe_mode", True)),
            "rate_limit_remaining": rate_limit_remaining,
            "timeline": timeline,
            "audit_events": [],
            "external_request_executed": False,
            "generated_at": utc_now(),
        }
        append_audit_event(
            "provider_failure_detected",
            requested_by,
            {"execution_id": execution_id, "reason": reason, "external_request_executed": False},
            risk="medium",
        )
        return self._save_and_enrich(result)

    def _records(self) -> list[dict]:
        payload = self._store.read({"records": [], "rate_limits": {}})
        return payload.get("records", [])

    def _execution_mode_for_payload(self, payload: dict) -> str:
        provider_id = self._clean_provider(payload.get("provider_id"))
        if provider_id is None or provider_id in economic_provider_ids():
            return "economic_low_cost"
        if payload.get("safe_mode", True):
            return "low_cost_safe"
        return "controlled_real_ai"

    def _save_and_enrich(self, result: dict) -> dict:
        def mutator(payload: dict) -> None:
            payload.setdefault("records", []).append(result)
            payload["records"] = payload["records"][-120:]

        self._store.update({"records": [], "rate_limits": {}}, mutator)
        return self._with_audit_preview(result)

    def _with_audit_preview(self, result: dict) -> dict:
        event_types = {
            "real_provider_execution_started",
            "provider_connected",
            "real_ai_execution_completed",
            "economic_provider_selected",
            "low_cost_execution_mode",
            "provider_execution_completed",
            "fallback_real_ai_triggered",
            "provider_failure_detected",
        }
        preview = []
        for event in read_audit_events(400):
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
        enriched.setdefault("model_used", None)
        enriched["audit_events"] = preview[-12:]
        return enriched

    def _clean_provider(self, value: object) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip().lower()
        return cleaned or None

    def _preview(self, value: str) -> str:
        compact = " ".join(value.split())
        return compact[:420] + ("..." if len(compact) > 420 else "")

    def _event(self, event: str, detail: str) -> dict:
        return {"timestamp": utc_now(), "event": event, "detail": detail}


real_provider_execution_engine = RealProviderExecutionEngine()
