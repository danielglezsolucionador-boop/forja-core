from __future__ import annotations

from pathlib import Path
import shutil
from concurrent.futures import ThreadPoolExecutor

from app.core.audit import read_audit_events
from app.core.storage import JsonStore
from app.services.file_generation_service import ControlledFileGenerator
from app.services.operational_loop_service import (
    BuildLoopManager,
    CorrectionLoopManager,
    DeliveryPackageManager,
    RetryPolicyManager,
    ValidationLoopManager,
)
from app.services.workspace_service import WorkspaceManager


def _build_manager(tmp_path: Path) -> BuildLoopManager:
    return BuildLoopManager(
        state_store=JsonStore(tmp_path / "state" / "build_loops.json"),
        base_dir=tmp_path,
        workspace_manager_override=WorkspaceManager(tmp_path),
        file_generator_override=ControlledFileGenerator(tmp_path),
    )


def _validation_manager(tmp_path: Path) -> ValidationLoopManager:
    return ValidationLoopManager(state_store=JsonStore(tmp_path / "state" / "validation_loops.json"), base_dir=tmp_path)


def _correction_manager(tmp_path: Path, validation: ValidationLoopManager | None = None) -> CorrectionLoopManager:
    return CorrectionLoopManager(
        validation_manager=validation or _validation_manager(tmp_path),
        state_store=JsonStore(tmp_path / "state" / "correction_loops.json"),
        base_dir=tmp_path,
    )


def _retry_manager(tmp_path: Path, max_retries: int = 3) -> RetryPolicyManager:
    return RetryPolicyManager(state_store=JsonStore(tmp_path / "state" / "retry_policy.json"), max_retries=max_retries)


def _delivery_manager(tmp_path: Path) -> DeliveryPackageManager:
    return DeliveryPackageManager(state_store=JsonStore(tmp_path / "state" / "delivery_packages.json"), base_dir=tmp_path)


def _start(manager: BuildLoopManager, text: str, request_id: str, manual_approval: bool = True) -> dict:
    return manager.start(
        {
            "sender": "ceo",
            "recipient": "forja",
            "input": text,
            "source_request_id": request_id,
            "manual_approval": manual_approval,
        }
    )


def test_build_loop_app_inventario(tmp_path: Path) -> None:
    record = _start(_build_manager(tmp_path), "creame una app de inventario", "phase61-app-inventario")
    assert record["state"] == "build_completed"
    assert record["request_type"] == "app"
    assert record["domain"] == "inventario"
    assert record["workspace"]["logical_path"] == ".forja/workspaces/phase61-app-inventario"
    assert any(output["label"] == "build_summary.md" for output in record["outputs"])


def test_build_loop_api_clientes(tmp_path: Path) -> None:
    record = _start(_build_manager(tmp_path), "creame una API para clientes", "phase61-api-clientes")
    assert record["state"] == "build_completed"
    assert record["request_type"] == "api"
    assert record["domain"] == "clientes"
    assert any(output["label"] == "main.py" for output in record["outputs"])


def test_build_loop_dashboard_financiero(tmp_path: Path) -> None:
    record = _start(_build_manager(tmp_path), "creame un dashboard financiero", "phase61-dashboard-financiero")
    assert record["state"] == "build_completed"
    assert record["request_type"] == "dashboard"
    assert record["domain"] == "financiero"
    assert "frontend" in record["generation"]["modules_created"]


def test_build_loop_module_autenticacion(tmp_path: Path) -> None:
    record = _start(_build_manager(tmp_path), "creame un modulo de autenticacion", "phase61-module-auth")
    assert record["state"] == "build_completed"
    assert record["request_type"] == "module"
    assert "module" in record["generation"]["modules_created"]


def test_build_loop_invalid_request_is_controlled(tmp_path: Path) -> None:
    record = _start(_build_manager(tmp_path), "hola", "phase61-invalid", manual_approval=False)
    assert record["state"] == "build_blocked"
    assert record["reason"] == "invalid_request"
    assert record["workspace"] is None


def test_build_loop_request_without_approval_waits(tmp_path: Path) -> None:
    record = _start(_build_manager(tmp_path), "creame una app de inventario", "phase61-no-approval", manual_approval=False)
    assert record["state"] == "approval_required"
    assert record["approval_status"] == "requested"
    assert record["workspace"] is None


def test_build_loop_approved_request_completes(tmp_path: Path) -> None:
    record = _start(_build_manager(tmp_path), "creame una API para clientes", "phase61-approved", manual_approval=True)
    assert record["state"] == "build_completed"
    assert record["approval_status"] == "approved"
    assert record["workspace"]["status"] == "created"
    assert record["generation"]["status"] == "completed"


def test_build_loop_complete_outputs_manifest_and_audit(tmp_path: Path) -> None:
    record = _start(_build_manager(tmp_path), "creame una app de inventario", "phase61-complete")
    workspace = tmp_path / ".forja" / "workspaces" / "phase61-complete"
    assert (workspace / "workspace_manifest.json").is_file()
    assert (workspace / "outputs" / "build_summary.md").is_file()
    assert (workspace / "audit" / "build_loop_record.json").is_file()
    assert (workspace / "audit" / "timeline.json").is_file()
    audit_types = {event["event_type"] for event in record["audit_events"]}
    assert {"build_loop_started", "build_step_completed", "build_loop_completed"}.issubset(audit_types)


def test_build_loop_timeline_contains_required_steps(tmp_path: Path) -> None:
    record = _start(_build_manager(tmp_path), "creame un dashboard financiero", "phase61-timeline")
    events = [item["event"] for item in record["timeline"]]
    assert "intent.ready" in events
    assert "blueprint.ready" in events
    assert "workspace.ready" in events
    assert "files.generated" in events
    assert events[-1] == "build.completed"


def test_validation_loop_valid_workspace_passes(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame una app de inventario", "phase62-valid")
    report = _validation_manager(tmp_path).validate({"build_record": build})
    assert report["passed"] is True
    assert report["severity"] == "low"
    assert report["failed_checks"] == []


def test_validation_loop_incomplete_workspace_fails(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame una app de inventario", "phase62-incomplete")
    shutil.rmtree(tmp_path / ".forja" / "workspaces" / "phase62-incomplete" / "frontend")
    report = _validation_manager(tmp_path).validate({"build_record": build})
    assert report["passed"] is False
    assert any(check["check"] == "frontend_exists" for check in report["failed_checks"])
    assert report["severity"] == "high"


def test_validation_loop_missing_readme_is_auto_fixable(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame una API para clientes", "phase62-readme")
    (tmp_path / ".forja" / "workspaces" / "phase62-readme" / "README.md").unlink()
    report = _validation_manager(tmp_path).validate({"build_record": build})
    assert report["passed"] is False
    assert any(check["check"] == "readme_exists" for check in report["failed_checks"])
    assert report["auto_fix_possible"] is True


def test_validation_loop_missing_blueprint_is_blocker(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame un dashboard financiero", "phase62-blueprint")
    (tmp_path / ".forja" / "workspaces" / "phase62-blueprint" / "blueprint.json").unlink()
    report = _validation_manager(tmp_path).validate({"build_record": build})
    assert report["passed"] is False
    assert report["severity"] == "blocker"
    assert report["auto_fix_possible"] is False


def test_validation_loop_missing_output_is_auto_fixable(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame un modulo de autenticacion", "phase62-output")
    output_dir = tmp_path / ".forja" / "workspaces" / "phase62-output" / "outputs"
    for path in output_dir.glob("*"):
        path.unlink()
    report = _validation_manager(tmp_path).validate({"build_record": build})
    assert report["passed"] is False
    assert any(check["check"] == "outputs_not_empty" for check in report["failed_checks"])
    assert report["auto_fix_possible"] is True


def test_validation_loop_missing_audit_is_auto_fixable(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame una app de inventario", "phase62-audit")
    shutil.rmtree(tmp_path / ".forja" / "workspaces" / "phase62-audit" / "audit")
    report = _validation_manager(tmp_path).validate({"build_record": build})
    assert report["passed"] is False
    assert any(check["check"] == "audit_generated" for check in report["failed_checks"])
    assert report["auto_fix_possible"] is True


def test_validation_loop_report_records_passed_and_failed(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame una app de inventario", "phase62-report")
    workspace = tmp_path / ".forja" / "workspaces" / "phase62-report"
    (workspace / "execution_report.md").unlink()
    report = _validation_manager(tmp_path).validate({"build_record": build})
    names = {check["check"] for check in report["checks"]}
    assert "workspace_exists" in names
    assert "execution_report_exists" in {check["check"] for check in report["failed_checks"]}
    assert (workspace / "audit" / "validation_report.json").is_file()


def test_validation_loop_blocker_detected_for_missing_workspace(tmp_path: Path) -> None:
    report = _validation_manager(tmp_path).validate({"request_id": "phase62-missing-workspace"})
    assert report["passed"] is False
    assert report["severity"] == "blocker"
    assert report["auto_fix_possible"] is False


def test_correction_loop_restores_missing_readme(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame una API para clientes", "phase63-readme")
    workspace = tmp_path / ".forja" / "workspaces" / "phase63-readme"
    (workspace / "README.md").unlink()
    validation = _validation_manager(tmp_path)
    report = validation.validate({"build_record": build})
    correction = _correction_manager(tmp_path, validation).correct({"validation_report": report, "sender": "ceo"})
    assert correction["state"] == "correction_completed"
    assert (workspace / "README.md").is_file()
    assert correction["revalidation"]["passed"] is True


def test_correction_loop_restores_missing_outputs(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame una app de inventario", "phase63-outputs")
    workspace = tmp_path / ".forja" / "workspaces" / "phase63-outputs"
    for path in (workspace / "outputs").glob("*"):
        path.unlink()
    validation = _validation_manager(tmp_path)
    report = validation.validate({"build_record": build})
    correction = _correction_manager(tmp_path, validation).correct({"validation_report": report, "sender": "ceo"})
    assert correction["state"] == "correction_completed"
    assert (workspace / "outputs" / "correction-placeholder.md").is_file()


def test_correction_loop_restores_missing_manifest(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame un dashboard financiero", "phase63-manifest")
    workspace = tmp_path / ".forja" / "workspaces" / "phase63-manifest"
    (workspace / "workspace_manifest.json").unlink()
    validation = _validation_manager(tmp_path)
    report = validation.validate({"build_record": build})
    correction = _correction_manager(tmp_path, validation).correct({"validation_report": report, "sender": "ceo"})
    assert correction["state"] == "correction_completed"
    assert (workspace / "workspace_manifest.json").is_file()


def test_correction_loop_blocks_architectural_failure(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame una app de inventario", "phase63-architecture")
    shutil.rmtree(tmp_path / ".forja" / "workspaces" / "phase63-architecture" / "frontend")
    report = _validation_manager(tmp_path).validate({"build_record": build})
    correction = _correction_manager(tmp_path).correct({"validation_report": report, "sender": "ceo"})
    assert correction["state"] == "correction_blocked"
    assert correction["blocked_fixes"] == ["auto_fix_not_allowed"]


def test_correction_loop_revalidation_can_fail_safely(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame una app de inventario", "phase63-revalidate-fail")
    workspace = tmp_path / ".forja" / "workspaces" / "phase63-revalidate-fail"
    (workspace / "README.md").unlink()
    (workspace / "blueprint.json").unlink()
    report = {
        "request_id": "phase63-revalidate-fail",
        "auto_fix_possible": True,
        "failed_checks": [{"check": "readme_exists", "passed": False, "detail": "README missing."}],
    }
    correction = _correction_manager(tmp_path).correct({"validation_report": report, "sender": "ceo"})
    assert correction["state"] == "correction_failed"
    assert correction["revalidation"]["severity"] == "blocker"


def test_correction_loop_audit_and_timeline(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame una API para clientes", "phase63-audit")
    workspace = tmp_path / ".forja" / "workspaces" / "phase63-audit"
    (workspace / "execution_report.md").unlink()
    validation = _validation_manager(tmp_path)
    report = validation.validate({"build_record": build})
    correction = _correction_manager(tmp_path, validation).correct({"validation_report": report, "sender": "ceo"})
    assert [event["event"] for event in correction["timeline"]][-1] == "correction.revalidated"
    assert (workspace / "audit" / "correction_report.json").is_file()
    audit_types = {event["event_type"] for event in read_audit_events(80)}
    assert {"correction_started", "safe_fix_applied", "correction_revalidated"}.issubset(audit_types)


def test_retry_policy_allows_minor_validation_retry(tmp_path: Path) -> None:
    record = _retry_manager(tmp_path).evaluate(
        {"operation_id": "phase64-allowed", "request_id": "phase64-allowed", "failure_type": "validation_failure", "retry_count": 0}
    )
    assert record["retry_allowed"] is True
    assert record["retry_count"] == 1
    assert record["failure_classification"] == "validation_failure"


def test_retry_policy_blocks_unsafe_retry(tmp_path: Path) -> None:
    record = _retry_manager(tmp_path).evaluate(
        {"operation_id": "phase64-unsafe", "request_id": "phase64-unsafe", "failure_type": "unsafe_operation", "retry_count": 0}
    )
    assert record["retry_allowed"] is False
    assert record["retry_blocked_reason"] == "unsafe_operation_not_retryable"


def test_retry_policy_max_retries_reached(tmp_path: Path) -> None:
    record = _retry_manager(tmp_path).evaluate(
        {"operation_id": "phase64-max", "request_id": "phase64-max", "failure_type": "validation_failure", "retry_count": 3}
    )
    assert record["retry_allowed"] is False
    assert record["retry_blocked_reason"] == "max_retries_reached"


def test_retry_policy_duplicate_blocked(tmp_path: Path) -> None:
    store = JsonStore(tmp_path / "state" / "retry_policy.json")
    store.write({"records": [{"operation_id": "phase64-duplicate", "state": "retry_started"}]})
    record = RetryPolicyManager(state_store=store).evaluate(
        {"operation_id": "phase64-duplicate", "request_id": "phase64-duplicate", "failure_type": "validation_failure"}
    )
    assert record["retry_allowed"] is False
    assert record["retry_blocked_reason"] == "duplicate_execution"


def test_retry_policy_classifies_unknown_path_failure_as_unsafe(tmp_path: Path) -> None:
    record = _retry_manager(tmp_path).evaluate(
        {"operation_id": "phase64-classify", "request_id": "phase64-classify", "failure_type": "custom", "reason": "path traversal blocked"}
    )
    assert record["failure_classification"] == "unsafe_operation"
    assert record["retry_allowed"] is False


def test_retry_policy_governance_failure_has_no_retry(tmp_path: Path) -> None:
    record = _retry_manager(tmp_path).evaluate(
        {"operation_id": "phase64-governance", "request_id": "phase64-governance", "failure_type": "governance_block"}
    )
    assert record["retry_allowed"] is False
    assert record["failure_classification"] == "governance_block"


def test_retry_policy_provider_timeout_allowed(tmp_path: Path) -> None:
    record = _retry_manager(tmp_path).evaluate(
        {"operation_id": "phase64-provider", "request_id": "phase64-provider", "failure_type": "provider_failure", "retry_reason": "provider timeout"}
    )
    assert record["retry_allowed"] is True
    assert record["failure_classification"] == "provider_failure"


def test_retry_policy_audit_and_timeline(tmp_path: Path) -> None:
    record = _retry_manager(tmp_path).evaluate(
        {"operation_id": "phase64-audit", "request_id": "phase64-audit", "failure_type": "generation_failure", "retry_count": 1}
    )
    assert record["timeline"][0]["event"] == "failure.classified"
    assert record["timeline"][-1]["event"] == "retry.completed"
    audit_types = {event["event_type"] for event in read_audit_events(80)}
    assert {"failure_classified", "retry_started", "retry_completed"}.issubset(audit_types)


def test_delivery_package_app_inventario(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame una app de inventario", "phase65-app")
    validation = _validation_manager(tmp_path).validate({"build_record": build})
    package = _delivery_manager(tmp_path).create({"build_record": build, "validation_report": validation})
    assert package["status"] == "completed"
    assert package["logical_path"] == ".forja/workspaces/phase65-app/delivery"
    assert len(package["files"]) == 9


def test_delivery_package_api_clientes(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame una API para clientes", "phase65-api")
    validation = _validation_manager(tmp_path).validate({"build_record": build})
    package = _delivery_manager(tmp_path).create({"build_record": build, "validation_report": validation})
    assert package["status"] == "completed"
    assert (tmp_path / ".forja" / "workspaces" / "phase65-api" / "delivery" / "blueprint.json").is_file()


def test_delivery_package_dashboard_financiero(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame un dashboard financiero", "phase65-dashboard")
    validation = _validation_manager(tmp_path).validate({"build_record": build})
    package = _delivery_manager(tmp_path).create({"build_record": build, "validation_report": validation})
    labels = {item["label"] for item in package["files"]}
    assert {"summary.md", "next_steps.md", "workspace_manifest.json"}.issubset(labels)


def test_delivery_summary_next_steps_manifest_and_audit_summary_created(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame una app de inventario", "phase65-files")
    validation = _validation_manager(tmp_path).validate({"build_record": build})
    _delivery_manager(tmp_path).create({"build_record": build, "validation_report": validation})
    delivery = tmp_path / ".forja" / "workspaces" / "phase65-files" / "delivery"
    assert (delivery / "summary.md").read_text(encoding="utf-8").startswith("# Delivery Summary")
    assert (delivery / "next_steps.md").read_text(encoding="utf-8").startswith("# Next Steps")
    assert (delivery / "workspace_manifest.json").is_file()
    assert (delivery / "audit_summary.md").is_file()


def test_delivery_package_exposes_reviewable_ui_payload(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame una API para clientes", "phase65-ui")
    validation = _validation_manager(tmp_path).validate({"build_record": build})
    package = _delivery_manager(tmp_path).create({"build_record": build, "validation_report": validation})
    assert package["status"] == "completed"
    assert all(item["logical_path"].startswith(".forja/workspaces/phase65-ui/delivery/") for item in package["files"])
    assert all("\\" not in item["logical_path"] for item in package["files"])


def test_delivery_package_audit_and_timeline(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame un dashboard financiero", "phase65-audit")
    validation = _validation_manager(tmp_path).validate({"build_record": build})
    package = _delivery_manager(tmp_path).create({"build_record": build, "validation_report": validation})
    assert package["timeline"][-1]["event"] == "delivery.created"
    assert (tmp_path / ".forja" / "workspaces" / "phase65-audit" / "audit" / "delivery_package_record.json").is_file()
    audit_types = {event["event_type"] for event in read_audit_events(100)}
    assert {"delivery_package_started", "delivery_package_created"}.issubset(audit_types)


def test_operational_loop_end_to_end_delivery_package(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame una app de inventario", "phase66-e2e-app")
    validation = _validation_manager(tmp_path).validate({"build_record": build})
    correction = _correction_manager(tmp_path).correct({"validation_report": validation, "sender": "ceo"})
    package = _delivery_manager(tmp_path).create({"build_record": build, "validation_report": validation, "correction_report": correction})
    assert build["state"] == "build_completed"
    assert validation["passed"] is True
    assert correction["state"] == "correction_blocked"
    assert package["status"] == "completed"


def test_operational_loop_workflow_whatsapp_workspace_delivery(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame un workflow WhatsApp", "phase66-workflow")
    validation = _validation_manager(tmp_path).validate({"build_record": build})
    package = _delivery_manager(tmp_path).create({"build_record": build, "validation_report": validation})
    assert build["state"] == "build_completed"
    assert build["request_type"] == "workflow"
    assert validation["passed"] is True
    assert package["status"] == "completed"


def test_operational_loop_small_failure_corrected_then_delivered(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame una API para clientes", "phase66-corrected")
    workspace = tmp_path / ".forja" / "workspaces" / "phase66-corrected"
    (workspace / "README.md").unlink()
    validation = _validation_manager(tmp_path).validate({"build_record": build})
    correction = _correction_manager(tmp_path).correct({"validation_report": validation, "sender": "ceo"})
    package = _delivery_manager(tmp_path).create({"build_record": build, "validation_report": correction["revalidation"], "correction_report": correction})
    assert correction["state"] == "correction_completed"
    assert correction["revalidation"]["passed"] is True
    assert package["status"] == "completed"


def test_operational_loop_blocking_failure_does_not_autofix(tmp_path: Path) -> None:
    build = _start(_build_manager(tmp_path), "creame una app de inventario", "phase66-blocker")
    shutil.rmtree(tmp_path / ".forja" / "workspaces" / "phase66-blocker")
    validation = _validation_manager(tmp_path).validate({"build_record": build})
    correction = _correction_manager(tmp_path).correct({"validation_report": validation, "sender": "ceo"})
    retry = _retry_manager(tmp_path).evaluate({"operation_id": "phase66-blocker", "failure_type": "workspace_failure"})
    assert validation["severity"] == "blocker"
    assert correction["state"] == "correction_blocked"
    assert retry["retry_allowed"] is False


def test_operational_loop_retry_success_and_blocked_cases(tmp_path: Path) -> None:
    manager = _retry_manager(tmp_path)
    allowed = manager.evaluate({"operation_id": "phase66-retry-ok", "failure_type": "validation_failure"})
    blocked = manager.evaluate({"operation_id": "phase66-retry-blocked", "failure_type": "unsafe_operation"})
    maxed = manager.evaluate({"operation_id": "phase66-retry-max", "failure_type": "validation_failure", "retry_count": 3})
    assert allowed["retry_allowed"] is True
    assert blocked["retry_allowed"] is False
    assert maxed["retry_blocked_reason"] == "max_retries_reached"


def test_operational_loop_duplicate_execution_blocked(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)
    first = _start(manager, "creame una app de inventario", "phase66-duplicate")
    second = _start(manager, "creame una app de inventario", "phase66-duplicate")
    assert first["state"] == "build_completed"
    assert second["state"] == "build_blocked"
    assert second["reason"] == "duplicate_execution"


def test_operational_loop_security_blocks_path_traversal(tmp_path: Path) -> None:
    record = _build_manager(tmp_path).start(
        {"sender": "ceo", "recipient": "forja", "input": "creame una app de inventario", "source_request_id": "../phase66-bad", "manual_approval": True}
    )
    retry = _retry_manager(tmp_path).evaluate({"operation_id": "phase66-security", "failure_type": "custom", "reason": "secret exposure attempt"})
    assert record["state"] == "build_blocked"
    assert record["reason"] == "unsafe_request_id"
    assert retry["failure_classification"] == "unsafe_operation"


def test_operational_loop_stress_multiple_concurrent_requests(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)
    commands = [
        ("creame una app de inventario", "phase66-stress-app"),
        ("creame una API para clientes", "phase66-stress-api"),
        ("creame un dashboard financiero", "phase66-stress-dashboard"),
        ("creame un modulo de autenticacion", "phase66-stress-module"),
    ]
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(lambda item: _start(manager, item[0], item[1]), commands))
    assert all(record["state"] == "build_completed" for record in records)
    assert len({record["request_id"] for record in records}) == 4
