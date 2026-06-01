from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _register_agent() -> tuple[dict, dict]:
    response = client.post(
        "/local-agent/agents",
        json={
            "agent_name": "FORJA Local Agent Test",
            "machine_label": "test-pc",
            "owner": "ceo",
            "capability_profile": [
                "repo_read",
                "repo_status",
                "repo_diff",
                "repo_edit_controlled",
                "repo_branch_create",
                "repo_commit_prepare",
                "memory_read",
                "reports_generate",
                "deliveries_generate",
                "logs_read",
                "build_run",
                "tests_run",
                "audit_run",
                "backup_create",
                "snapshot_create",
                "rollback_plan",
                "artifact_upload",
            ],
            "allowed_repositories": ["forja"],
            "allowed_workspaces": ["ecosystem"],
        },
    )
    assert response.status_code == 200
    agent = response.json()
    assert agent["agent_token"].startswith("forja_agent_v1_")
    assert "token_hash" not in agent
    headers = {"Authorization": f"Bearer {agent['agent_token']}", "X-FORJA-Agent-Id": agent["agent_id"]}
    return agent, headers


def _snapshot_payload() -> dict:
    return {
        "snapshot": {
            "machine": {"label": "test-pc", "agent_version": "1.0.0"},
            "repositories": [{"repo_id": "forja", "branch": "main", "head": "test", "dirty": False}],
            "memory_sources": [{"path": "docs/ecosystem-memory/core/FORJA_PHASE2_DECISION_TRACE.md", "exists": True}],
        }
    }


def test_local_agent_registers_polls_executes_read_task_end_to_end() -> None:
    _, headers = _register_agent()

    created = client.post(
        "/local-agent/tasks",
        json={
            "instruction": "Auditar repositorio FORJA con git status y memoria",
            "title": "Auditoria local agent e2e",
            "requested_by": "ceo",
            "target": {"workspace_id": "ecosystem", "repo_ids": ["forja"], "paths": []},
        },
    )
    assert created.status_code == 200
    task = created.json()
    assert task["status"] == "queued"
    assert task["policy"]["requires_snapshot"] is True
    assert task["policy"]["requires_backup"] is False

    poll = client.post(
        "/agent/v1/tasks/poll",
        headers=headers,
        json={"capabilities": task["capabilities_required"], "available_repositories": ["forja"], "max_tasks": 1},
    )
    assert poll.status_code == 200
    assert poll.json()["tasks"][0]["task_id"] == task["task_id"]

    lease = client.post(f"/agent/v1/tasks/{task['task_id']}/lease", headers=headers)
    assert lease.status_code == 200
    assert lease.json()["task"]["status"] == "leased"

    snapshot = client.post(f"/agent/v1/tasks/{task['task_id']}/snapshot", headers=headers, json=_snapshot_payload())
    assert snapshot.status_code == 200
    assert snapshot.json()["status"] == "running"

    log = client.post(
        f"/agent/v1/tasks/{task['task_id']}/logs",
        headers=headers,
        json={
            "command_log": {
                "cwd": "C:/Users/admin/Desktop/forja",
                "command_sanitized": "git status --short",
                "exit_code": 0,
                "stdout_preview": "",
                "stderr_preview": "",
                "secrets_redacted": True,
            }
        },
    )
    assert log.status_code == 200

    result = client.post(
        f"/agent/v1/tasks/{task['task_id']}/results",
        headers=headers,
        json={
            "result": {
                "status": "completed",
                "summary": "Auditoria local completada.",
                "human_cabin_summary": "Local Agent completo auditoria.",
                "technical_summary": {"commands_run": 1, "commands_failed": 0},
                "secrets_exposed": False,
            }
        },
    )
    assert result.status_code == 200
    payload = result.json()
    assert payload["status"] == "completed"
    assert payload["result"]["secrets_exposed"] is False
    assert any(event["event_type"] == "task.snapshot.created" for event in payload["history"])
    assert any(event["event_type"] == "task.completed" for event in payload["history"])


def test_local_agent_requires_approval_backup_and_rollback_for_controlled_edits() -> None:
    _, headers = _register_agent()

    created = client.post(
        "/local-agent/tasks",
        json={
            "instruction": "Corregir codigo controlado en FORJA",
            "title": "Cambio controlado local",
            "requested_by": "ceo",
            "target": {"workspace_id": "ecosystem", "repo_ids": ["forja"], "paths": ["apps/backend/app/api/routes/runtime.py"]},
        },
    )
    assert created.status_code == 200
    task = created.json()
    assert task["status"] == "awaiting_human_approval"
    assert task["policy"]["requires_backup"] is True
    assert task["policy"]["requires_rollback_plan"] is True
    assert task["policy"]["push_automatic"] is False
    assert task["policy"]["deploy_automatic"] is False

    approved = client.post(
        f"/local-agent/tasks/{task['task_id']}/approve",
        json={"approved_by": "ceo", "reason": "Validacion e2e de cambio controlado."},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "queued"

    lease = client.post(f"/agent/v1/tasks/{task['task_id']}/lease", headers=headers)
    assert lease.status_code == 200

    snapshot = client.post(f"/agent/v1/tasks/{task['task_id']}/snapshot", headers=headers, json=_snapshot_payload())
    assert snapshot.status_code == 200
    assert snapshot.json()["status"] == "backing_up"

    blocked_result = client.post(
        f"/agent/v1/tasks/{task['task_id']}/results",
        headers=headers,
        json={"result": {"status": "completed", "summary": "Should fail", "secrets_exposed": False}},
    )
    assert blocked_result.status_code == 409
    assert blocked_result.json()["detail"] == "backup_required_before_result"

    backup = client.post(
        f"/agent/v1/tasks/{task['task_id']}/backup",
        headers=headers,
        json={
            "backup": {
                "local_path": "D:/ECOSYSTEM/FORJA_LOCAL_AGENT/runs/test/backup.zip",
                "sha256": "abc123",
                "validated": True,
                "secrets_found": False,
                "excluded": [".git", "node_modules", "build", "dist", ".env", "secrets"],
            }
        },
    )
    assert backup.status_code == 200

    blocked_without_rollback = client.post(
        f"/agent/v1/tasks/{task['task_id']}/results",
        headers=headers,
        json={"result": {"status": "completed", "summary": "Should fail", "secrets_exposed": False}},
    )
    assert blocked_without_rollback.status_code == 409
    assert blocked_without_rollback.json()["detail"] == "rollback_required_before_result"

    rollback = client.post(
        f"/agent/v1/tasks/{task['task_id']}/rollback-record",
        headers=headers,
        json={
            "rollback": {
                "available": True,
                "strategy": "restore_files_from_backup",
                "requires_human_confirmation": True,
                "validation_commands": ["git diff", "python -m pytest -q"],
            }
        },
    )
    assert rollback.status_code == 200

    result = client.post(
        f"/agent/v1/tasks/{task['task_id']}/results",
        headers=headers,
        json={
            "result": {
                "status": "completed",
                "summary": "Cambio controlado preparado con backup y rollback.",
                "human_cabin_summary": "Local Agent dejo cambio controlado trazado.",
                "technical_summary": {"commands_run": 0, "commands_failed": 0},
                "secrets_exposed": False,
            }
        },
    )
    assert result.status_code == 200
    payload = result.json()
    assert payload["status"] == "completed"
    assert payload["backups"]
    assert payload["rollback"]["available"] is True


def test_local_agent_blocks_push_without_critical_approval_and_rejects_secret_payloads() -> None:
    _, headers = _register_agent()
    created = client.post(
        "/local-agent/tasks",
        json={
            "instruction": "Hacer push origin main",
            "title": "Push critico",
            "requested_by": "ceo",
            "target": {"workspace_id": "ecosystem", "repo_ids": ["forja"], "paths": []},
        },
    )
    assert created.status_code == 200
    task = created.json()
    assert task["status"] == "awaiting_critical_approval"
    assert task["policy"]["requires_critical_approval"] is True
    assert task["policy"]["push_automatic"] is False

    normal_approval = client.post(
        f"/local-agent/tasks/{task['task_id']}/approve",
        json={"approved_by": "ceo", "reason": "This must not bypass critical gate."},
    )
    assert normal_approval.status_code == 409
    assert normal_approval.json()["detail"] == "critical_approval_required"

    poll = client.post(
        "/agent/v1/tasks/poll",
        headers=headers,
        json={"capabilities": task["capabilities_required"], "available_repositories": ["forja"], "max_tasks": 1},
    )
    assert poll.status_code == 200
    assert all(item["task_id"] != task["task_id"] for item in poll.json()["tasks"])

    approved = client.post(
        f"/local-agent/tasks/{task['task_id']}/critical-approval",
        json={"approved_by": "ceo", "reason": "Solo validar gate critico.", "action": "push", "exact_target": {"remote": "origin", "branch": "main"}},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "queued"

    lease = client.post(f"/agent/v1/tasks/{task['task_id']}/lease", headers=headers)
    assert lease.status_code == 200

    secret_snapshot = client.post(
        f"/agent/v1/tasks/{task['task_id']}/snapshot",
        headers=headers,
        json={"snapshot": {"note": "sk-this-must-not-pass"}},
    )
    assert secret_snapshot.status_code == 409
    assert secret_snapshot.json()["detail"] == "payload_contains_secret"


def test_local_agent_dashboard_feeds_human_cabin_runtime_snapshot() -> None:
    dashboard = client.get("/local-agent/dashboard")
    assert dashboard.status_code == 200
    assert "tasks" in dashboard.json()

    runtime = client.get("/runtime/status")
    assert runtime.status_code == 200
    snapshot = runtime.json()["snapshot"]
    assert "localAgent" in snapshot
    assert "metrics" in snapshot
    assert "activity" in snapshot
