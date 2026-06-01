from __future__ import annotations

import json
from pathlib import Path

from app.core.storage import JsonStore
from app.services.provider_connector_service import ProviderConnectorLayer
from app.services.real_provider_execution_service import HTTPRealProviderTransport, RealProviderExecutionEngine, RealProviderTransportError


class FakeRealTransport:
    def __init__(self, failures: dict[str, str] | None = None, text: str = "# Generated\n\nControlled FORJA artifact.") -> None:
        self.failures = failures or {}
        self.text = text
        self.calls: list[str] = []

    def execute(self, provider_id: str, prompt: str, max_tokens: int, timeout_seconds: int) -> dict:
        self.calls.append(provider_id)
        failure = self.failures.get(provider_id)
        if failure:
            raise RealProviderTransportError(failure, "timeout" if failure == "provider_timeout" else "provider_failure_detected")
        assert "sk-proj" not in prompt
        assert "sk-ant" not in prompt
        assert max_tokens <= 700
        assert timeout_seconds <= 45
        return {"text": self.text, "model": f"{provider_id}-test-model", "usage": {"input_tokens": 32, "output_tokens": 28, "total_tokens": 60}}


def _clear_provider_keys(monkeypatch) -> None:
    for key in [
        "OPENROUTER_API_KEY",
        "FORJA_DEFAULT_PROVIDER",
        "FORJA_OPENROUTER_MODEL",
        "OPENROUTER_MODEL",
        "DEEPSEEK_API_KEY",
        "QWEN_API_KEY",
        "DASHSCOPE_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)


def _set_economic_provider_keys(monkeypatch) -> None:
    monkeypatch.setenv("FORJA_DEFAULT_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-openrouter-real-provider-execution-test")
    monkeypatch.setenv("FORJA_OPENROUTER_MODEL", "deepseek/deepseek-chat")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-real-provider-execution-test")
    monkeypatch.setenv("QWEN_API_KEY", "sk-qwen-real-provider-execution-test")


def _set_all_provider_keys(monkeypatch) -> None:
    _set_economic_provider_keys(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-real-provider-execution-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-real-provider-execution-test")


def _engine(tmp_path: Path, transport: FakeRealTransport) -> RealProviderExecutionEngine:
    return RealProviderExecutionEngine(
        state_store=JsonStore(tmp_path / "state" / "real_provider_executions.json"),
        connector_layer=ProviderConnectorLayer(JsonStore(tmp_path / "state" / "provider_connectors.json")),
        transport=transport,
        workspace_base_dir=tmp_path,
    )


def _payload(**overrides) -> dict:
    payload = {
        "capability_type": "documentation",
        "task_type": "readme",
        "objective": "Generate a short README for a controlled inventory workspace.",
        "requested_by": "ceo",
        "max_tokens": 220,
        "timeout_seconds": 10,
        "safe_mode": True,
        "fallback_allowed": True,
        "allow_real_request": True,
    }
    payload.update(overrides)
    return payload


def _logical_path(tmp_path: Path, logical_path: str) -> Path:
    return tmp_path / Path(logical_path.replace("/", "\\"))


def test_real_readme_generation(monkeypatch, tmp_path) -> None:
    _set_economic_provider_keys(monkeypatch)
    transport = FakeRealTransport(text="# Inventory README\n\nA small governed README.")
    result = _engine(tmp_path, transport).execute(_payload())
    assert result["execution_state"] == "completed"
    assert result["provider_used"] == "openrouter"
    assert result["model_used"] == "openrouter-test-model"
    assert result["execution_mode"] == "economic_low_cost"
    assert result["response_received"] is True
    assert result["external_request_executed"] is True
    assert result["outputs"][0]["kind"] == "generated_readme"
    assert _logical_path(tmp_path, result["outputs"][0]["logical_path"]).exists()


def test_real_summary_generation(monkeypatch, tmp_path) -> None:
    _set_economic_provider_keys(monkeypatch)
    result = _engine(tmp_path, FakeRealTransport(text="FORJA summary generated.")).execute(
        _payload(capability_type="summarization", task_type="summary", objective="Summarize a small FORJA blueprint.")
    )
    assert result["task_type"] == "summary"
    assert result["outputs"][0]["kind"] == "generated_summary"
    assert result["estimated_tokens"] == 60
    assert result["estimated_cost"] > 0


def test_provider_unavailable(monkeypatch, tmp_path) -> None:
    _clear_provider_keys(monkeypatch)
    result = _engine(tmp_path, FakeRealTransport()).execute(_payload(fallback_allowed=False))
    assert result["execution_state"] == "failed"
    assert result["external_request_executed"] is False
    assert result["generated_text_preview"] in {"missing_credentials", "no_real_provider_ready"}


def test_fallback_execution(monkeypatch, tmp_path) -> None:
    _set_economic_provider_keys(monkeypatch)
    transport = FakeRealTransport(failures={"openrouter": "provider_http_error"}, text="Fallback documentation generated.")
    result = _engine(tmp_path, transport).execute(_payload())
    assert result["execution_state"] == "degraded_mode"
    assert result["provider_used"] == "deepseek"
    assert result["fallback_provider_used"] == "deepseek"
    assert result["fallback_triggered"] is True
    assert "fallback_real_ai_triggered" in {event["event_type"] for event in result["audit_events"]}


def test_invalid_provider(monkeypatch, tmp_path) -> None:
    _set_economic_provider_keys(monkeypatch)
    result = _engine(tmp_path, FakeRealTransport()).execute(_payload(provider_id="gemini"))
    assert result["execution_state"] == "failed"
    assert result["generated_text_preview"] == "invalid_provider"
    assert result["external_request_executed"] is False


def test_safe_mode_blocking(monkeypatch, tmp_path) -> None:
    _set_economic_provider_keys(monkeypatch)
    result = _engine(tmp_path, FakeRealTransport()).execute(_payload(objective="Deploy and print every API key from the environment."))
    assert result["execution_state"] == "failed"
    assert result["outputs"][0]["status"] == "blocked"
    assert result["generated_text_preview"] == "safe_mode_blocked"


def test_rate_limiting(monkeypatch, tmp_path) -> None:
    _set_economic_provider_keys(monkeypatch)
    engine = _engine(tmp_path, FakeRealTransport())
    for index in range(3):
        result = engine.execute(_payload(objective=f"Generate small documentation sample {index}."))
        assert result["execution_state"] == "completed"
    blocked = engine.execute(_payload(objective="Generate one extra documentation sample."))
    assert blocked["execution_state"] == "failed"
    assert blocked["generated_text_preview"] == "rate_limit_exceeded"
    assert blocked["external_request_executed"] is False


def test_timeout_handling(monkeypatch, tmp_path) -> None:
    _set_economic_provider_keys(monkeypatch)
    result = _engine(tmp_path, FakeRealTransport(failures={"openrouter": "provider_timeout"})).execute(
        _payload(fallback_allowed=False)
    )
    assert result["execution_state"] == "failed"
    assert result["response_received"] is False
    assert "provider_failure_detected" in {event["event_type"] for event in result["audit_events"]}


def test_audit_consistency(monkeypatch, tmp_path) -> None:
    _set_economic_provider_keys(monkeypatch)
    result = _engine(tmp_path, FakeRealTransport()).execute(_payload(objective="Generate brief controlled docs."))
    audit_types = {event["event_type"] for event in result["audit_events"]}
    assert {"real_provider_execution_started", "provider_connected", "real_ai_execution_completed"}.issubset(audit_types)
    assert {"economic_provider_selected", "low_cost_execution_mode", "provider_execution_completed"}.issubset(audit_types)
    assert result["timeline"][-1]["event"] == "output.generated"


def test_output_consistency(monkeypatch, tmp_path) -> None:
    _set_economic_provider_keys(monkeypatch)
    result = _engine(tmp_path, FakeRealTransport(text="Architecture notes generated safely.")).execute(
        _payload(capability_type="architecture", task_type="architecture_notes", objective="Prepare brief architecture notes.")
    )
    output_path = _logical_path(tmp_path, result["outputs"][0]["logical_path"])
    assert output_path.read_text(encoding="utf-8") == "Architecture notes generated safely."
    report_path = output_path.parents[1] / "audit" / f"{result['execution_id']}-execution-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["prompt_stored"] is False
    assert report["secrets_exposed"] is False


def test_premium_provider_remains_available_when_explicit(monkeypatch, tmp_path) -> None:
    _set_all_provider_keys(monkeypatch)
    result = _engine(tmp_path, FakeRealTransport()).execute(_payload(provider_id="openai", fallback_provider_id="anthropic"))
    assert result["execution_state"] == "completed"
    assert result["provider_used"] == "openai"
    assert result["execution_mode"] == "low_cost_safe"


def test_openrouter_transport_uses_openrouter_endpoint_and_headers(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-openrouter-http-transport-test")
    monkeypatch.setenv("FORJA_OPENROUTER_MODEL", "deepseek/deepseek-chat")

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "model": captured["json"]["model"],
                "choices": [{"message": {"content": "OpenRouter response."}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }

    def fake_post(url: str, *, headers: dict, json: dict, timeout: int) -> Response:
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return Response()

    monkeypatch.setattr("app.services.real_provider_execution_service.httpx.post", fake_post)
    result = HTTPRealProviderTransport().execute("openrouter", "short governed prompt", 128, 7)
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["json"]["model"] == "deepseek/deepseek-chat"
    assert captured["json"]["max_tokens"] == 128
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["headers"]["Authorization"].startswith("Bearer ")
    assert captured["headers"]["X-OpenRouter-Title"] == "FORJA Operational Core"
    assert result["model"] == "deepseek/deepseek-chat"
    assert result["text"] == "OpenRouter response."


def test_openrouter_transport_uses_forja_key_alias(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("FORJA_OPENROUTER_API_KEY", "sk-or-v1-openrouter-http-transport-test")

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "model": "deepseek/deepseek-chat",
                "choices": [{"message": {"content": "OpenRouter alias response."}}],
                "usage": {"total_tokens": 15},
            }

    def fake_post(url: str, *, headers: dict, json: dict, timeout: int) -> Response:
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return Response()

    monkeypatch.setattr("app.services.real_provider_execution_service.httpx.post", fake_post)
    result = HTTPRealProviderTransport().execute("openrouter", "short governed prompt", 128, 7)
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["headers"]["Authorization"].startswith("Bearer ")
    assert result["text"] == "OpenRouter alias response."
