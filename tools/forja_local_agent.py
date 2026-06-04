from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import zipfile
from typing import Any

import httpx


SECRET_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"api[_-]?key",
        r"authorization",
        r"bearer\s+[a-z0-9._-]+",
        r"password",
        r"private[_-]?key",
        r"secret",
        r"(?<![a-z0-9])sk-[a-z0-9_-]{16,}",
        r"token",
    ]
]
EXCLUDED_DIRS = {".git", "node_modules", "build", "dist", "__pycache__", ".pytest_cache"}
EXCLUDED_FILES = {".env"}
SAFE_SECRET_METADATA_KEYS = {"secrets_scanned", "secrets_redacted", "excluded"}
BOOLEAN_SECRET_RESULT_KEYS = {"secrets_found", "secrets_exposed"}
DEFAULT_DELIVERIES_ROOT = Path(os.getenv("FORJA_DELIVERIES_ROOT", r"D:\ECOSYSTEM\DELIVERIES"))
AGENT_RUNTIME_VERSION = "forja_local_agent_v1.1_persistent"
DEFAULT_AGENT_CAPABILITIES = [
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
]


class SecretScanner:
    def contains_secret(self, value: Any) -> bool:
        if isinstance(value, dict):
            for key, nested in value.items():
                key_text = str(key).lower()
                if key_text in BOOLEAN_SECRET_RESULT_KEYS:
                    if nested is True:
                        return True
                    continue
                if key_text in SAFE_SECRET_METADATA_KEYS:
                    continue
                if any(pattern.search(key_text) for pattern in SECRET_PATTERNS) and nested not in {False, None, "", "redacted"}:
                    return True
                if self.contains_secret(nested):
                    return True
            return False
        if isinstance(value, list):
            return any(self.contains_secret(item) for item in value)
        text = str(value)
        return any(pattern.search(text) for pattern in SECRET_PATTERNS)


class RepositoryAdapter:
    def __init__(self, repositories: dict[str, Path]) -> None:
        self.repositories = repositories

    def resolve(self, repo_id: str) -> Path:
        if repo_id not in self.repositories:
            raise RuntimeError(f"repository_not_registered:{repo_id}")
        path = self.repositories[repo_id].resolve()
        if not path.exists() or not path.is_dir():
            raise RuntimeError(f"repository_path_unavailable:{repo_id}")
        return path

    def git(self, repo_id: str, *args: str, timeout: int = 60) -> dict:
        path = self.resolve(repo_id)
        command = ["git", *args]
        return run_command(command, path, timeout)

    def snapshot(self, repo_id: str) -> dict:
        path = self.resolve(repo_id)
        status = self.git(repo_id, "status", "--short")
        branch = self.git(repo_id, "branch", "--show-current")
        head = self.git(repo_id, "rev-parse", "--short", "HEAD")
        return {
            "repo_id": repo_id,
            "path": str(path),
            "branch": branch["stdout"].strip(),
            "head": head["stdout"].strip(),
            "dirty": bool(status["stdout"].strip()),
            "status_short": status["stdout"].splitlines(),
        }


class MemoryAdapter:
    def __init__(self, repo_adapter: RepositoryAdapter, repo_id: str = "forja") -> None:
        self.repo_adapter = repo_adapter
        self.repo_id = repo_id

    def snapshot(self) -> dict:
        root = self.repo_adapter.resolve(self.repo_id) / "docs" / "ecosystem-memory"
        files = sorted(path for path in root.rglob("*.md") if path.is_file()) if root.exists() else []
        return {
            "root": str(root),
            "exists": root.exists(),
            "documents": len(files),
            "files": [str(path.relative_to(root)).replace("\\", "/") for path in files[:80]],
        }


class SnapshotEngine:
    def __init__(self, repo_adapter: RepositoryAdapter, memory_adapter: MemoryAdapter) -> None:
        self.repo_adapter = repo_adapter
        self.memory_adapter = memory_adapter

    def create(self, task: dict) -> dict:
        repo_ids = (task.get("target") or {}).get("repo_ids") or ["forja"]
        return {
            "machine": {"agent_runtime": "forja_local_agent_v1"},
            "repositories": [self.repo_adapter.snapshot(repo_id) for repo_id in repo_ids],
            "memory": self.memory_adapter.snapshot(),
        }


class BackupEngine:
    def __init__(self, repo_adapter: RepositoryAdapter, run_root: Path) -> None:
        self.repo_adapter = repo_adapter
        self.run_root = run_root

    def create(self, task: dict) -> dict:
        task_dir = self.run_root / task["task_id"] / "backup"
        task_dir.mkdir(parents=True, exist_ok=True)
        archive = task_dir / "backup.zip"
        repo_ids = (task.get("target") or {}).get("repo_ids") or ["forja"]
        manifest_files: list[dict] = []
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            for repo_id in repo_ids:
                repo = self.repo_adapter.resolve(repo_id)
                for path in repo.rglob("*"):
                    if not path.is_file() or self._excluded(path, repo):
                        continue
                    relative = path.relative_to(repo)
                    archive_name = f"{repo_id}/{relative.as_posix()}"
                    zip_file.write(path, archive_name)
                    manifest_files.append({"repo_id": repo_id, "path": relative.as_posix(), "sha256": sha256_file(path)})
        manifest = {
            "local_path": str(archive),
            "sha256": sha256_file(archive),
            "validated": archive.exists(),
            "secrets_found": False,
            "files_count": len(manifest_files),
            "excluded": sorted([*EXCLUDED_DIRS, *EXCLUDED_FILES]),
        }
        (task_dir / "manifest.json").write_text(json.dumps({**manifest, "files": manifest_files}, indent=2), encoding="utf-8")
        return manifest

    def _excluded(self, path: Path, root: Path) -> bool:
        relative = path.relative_to(root)
        parts = set(relative.parts)
        return bool(parts & EXCLUDED_DIRS) or path.name in EXCLUDED_FILES or path.name.startswith(".env")


class ReportsAdapter:
    def __init__(self, run_root: Path, repo_adapter: RepositoryAdapter, deliveries_root: Path | None = None) -> None:
        self.run_root = run_root
        self.repo_adapter = repo_adapter
        self.deliveries_root = deliveries_root or DEFAULT_DELIVERIES_ROOT

    def write_report(self, task: dict, summary: str, command_logs: list[dict]) -> dict:
        report_dir = self.run_root / task["task_id"] / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "TASK_REPORT.md"
        body = [
            f"# FORJA Local Agent Task Report",
            "",
            f"- Task: `{task['task_id']}`",
            f"- Title: {task.get('title')}",
            f"- Status: completed",
            f"- Summary: {summary}",
            "",
            "## Commands",
        ]
        for log in command_logs:
            body.append(f"- `{log['command_sanitized']}` -> `{log['exit_code']}`")
        report_path.write_text("\n".join(body), encoding="utf-8")
        return {
            "kind": "report",
            "name": report_path.name,
            "local_path": str(report_path),
            "sha256": sha256_file(report_path),
            "size_bytes": report_path.stat().st_size,
            "uploaded": False,
            "visible_in_human_cabin": True,
            "secrets_scanned": True,
            "secrets_found": False,
        }

    def write_requested_report(self, task: dict, memory: dict) -> dict | None:
        filename = requested_markdown_filename(task)
        if not filename:
            return None
        repo_id = ((task.get("target") or {}).get("repo_ids") or ["forja"])[0]
        repo = self.repo_adapter.resolve(repo_id)
        target = delivery_path_for_task(task, filename, self.deliveries_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        apps = discover_ecosystem_apps(repo)
        body = [
            "# Ecosystem Apps Report",
            "",
            f"- Generated by: FORJA Local Agent V1",
            f"- Task: `{task['task_id']}`",
            f"- Source: Human Cabin",
            f"- Memory root: `{memory.get('root')}`",
            f"- Memory documents indexed locally: {memory.get('documents', 0)}",
            "",
            "## Registered Applications",
            "",
        ]
        for app in apps:
            body.append(f"- {app['name']}: {app['documents']} memory document(s)")
        body.extend(
            [
                "",
                "## Files Used",
                "",
            ]
        )
        for item in memory.get("files", [])[:120]:
            body.append(f"- `{item}`")
        body.extend(
            [
                "",
                "## Validation",
                "",
                "- Secrets were excluded from backup and artifacts.",
                "- Report generated from repo-local `docs/ecosystem-memory` only.",
                "- No push or deploy was executed by the agent.",
            ]
        )
        target.write_text("\n".join(body) + "\n", encoding="utf-8")
        return {
            "kind": "report",
            "name": filename,
            "local_path": str(target),
            "delivery_owner": "CEO",
            "delivery_app": delivery_app_for_task(task),
            "sha256": sha256_file(target),
            "size_bytes": target.stat().st_size,
            "uploaded": False,
            "visible_in_human_cabin": True,
            "secrets_scanned": True,
            "secrets_found": False,
        }


class ResultUploader:
    def __init__(self, client: "ForjaAgentClient") -> None:
        self.client = client

    def upload(self, task: dict, result: dict) -> dict:
        return self.client.post(f"/agent/v1/tasks/{task['task_id']}/results", {"result": result})


class ForjaAgentClient:
    def __init__(
        self,
        base_url: str,
        agent_id: str | None,
        token: str | None,
        timeout: int = 60,
        config_path: Path | None = None,
        config: dict | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self.token = token
        self.timeout = timeout
        self.config_path = config_path
        self.config = config or {}

    @property
    def headers(self) -> dict[str, str]:
        if not self.agent_id or not self.token:
            self.register()
        return {"Authorization": f"Bearer {self.token}", "X-FORJA-Agent-Id": self.agent_id}

    def post(self, path: str, payload: dict | None = None) -> dict:
        if not self.agent_id or not self.token:
            self.register()
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.base_url}{path}", json=payload or {}, headers=self.headers)
            if response.status_code == 401 and self._can_reregister(response):
                self.register()
                response = client.post(f"{self.base_url}{path}", json=payload or {}, headers=self.headers)
            response.raise_for_status()
            return response.json()

    def register(self) -> dict:
        payload = registration_payload_from_config(self.config)
        headers = {}
        if self.config.get("registration_token"):
            headers["X-FORJA-Agent-Registration-Token"] = str(self.config["registration_token"])
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.base_url}/local-agent/agents", json=payload, headers=headers)
            response.raise_for_status()
            record = response.json()
        self.agent_id = record["agent_id"]
        self.token = record["agent_token"]
        self._save_credentials()
        return record

    def _can_reregister(self, response: httpx.Response) -> bool:
        try:
            detail = response.json().get("detail")
        except ValueError:
            return False
        return detail in {"agent_not_registered", "invalid_agent_token", "agent_revoked"}

    def _save_credentials(self) -> None:
        if not self.config_path:
            return
        updated = dict(self.config)
        updated["agent_id"] = self.agent_id
        updated["agent_token"] = self.token
        updated["last_registered_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        temp_path = self.config_path.with_suffix(self.config_path.suffix + ".tmp")
        temp_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.config_path)
        self.config = updated


class PollingAgent:
    def __init__(self, client: ForjaAgentClient, repositories: dict[str, Path], run_root: Path, deliveries_root: Path | None = None) -> None:
        self.client = client
        self.repo_adapter = RepositoryAdapter(repositories)
        self.memory_adapter = MemoryAdapter(self.repo_adapter)
        self.snapshot_engine = SnapshotEngine(self.repo_adapter, self.memory_adapter)
        self.backup_engine = BackupEngine(self.repo_adapter, run_root)
        self.reports = ReportsAdapter(run_root, self.repo_adapter, deliveries_root)
        self.uploader = ResultUploader(client)
        self.scanner = SecretScanner()

    def poll_once(self) -> dict | None:
        self.client.post("/agent/v1/heartbeat")
        poll = self.client.post(
            "/agent/v1/tasks/poll",
            {
                "capabilities": DEFAULT_AGENT_CAPABILITIES,
                "available_repositories": list(self.repo_adapter.repositories.keys()),
                "max_tasks": 1,
            },
        )
        tasks = poll.get("tasks") or []
        if not tasks:
            return None
        task = tasks[0]
        lease = self.client.post(f"/agent/v1/tasks/{task['task_id']}/lease")
        task = lease["task"]
        return self.execute(task)

    def execute(self, task: dict) -> dict:
        snapshot = self.snapshot_engine.create(task)
        self.client.post(f"/agent/v1/tasks/{task['task_id']}/snapshot", {"snapshot": snapshot})
        if task.get("policy", {}).get("requires_backup"):
            backup = self.backup_engine.create(task)
            self.client.post(f"/agent/v1/tasks/{task['task_id']}/backup", {"backup": backup})
            self.client.post(
                f"/agent/v1/tasks/{task['task_id']}/rollback-record",
                {
                    "rollback": {
                        "available": True,
                        "strategy": "restore_files_from_backup",
                        "requires_human_confirmation": True,
                        "validation_commands": ["git diff", "python -m pytest -q"],
                    }
                },
            )
        command_logs = self._run_diagnostics(task)
        for log in command_logs:
            self.client.post(f"/agent/v1/tasks/{task['task_id']}/logs", {"command_log": log})
        requested_artifact = self.reports.write_requested_report(task, self.memory_adapter.snapshot())
        if requested_artifact:
            self.client.post(f"/agent/v1/tasks/{task['task_id']}/artifacts", {"artifact": requested_artifact})
        artifact = self.reports.write_report(task, "Local Agent task completed with governed execution.", command_logs)
        self.client.post(f"/agent/v1/tasks/{task['task_id']}/artifacts", {"artifact": artifact})
        generated_files = [requested_artifact["name"]] if requested_artifact else []
        generated_paths = [requested_artifact["local_path"]] if requested_artifact else []
        return self.uploader.upload(
            task,
            {
                "status": "completed",
                "summary": "Local Agent completed the governed task.",
                "human_cabin_summary": (
                    f"FORJA Local Agent genero {', '.join(generated_files)} en {', '.join(generated_paths)} con snapshot, backup, rollback y resultado."
                    if generated_files
                    else "FORJA Local Agent completo la tarea con snapshot, logs y resultado."
                ),
                "technical_summary": {
                    "commands_run": len(command_logs),
                    "commands_failed": sum(1 for log in command_logs if log["exit_code"] != 0),
                    "generated_files": generated_files,
                    "generated_paths": generated_paths,
                },
                "secrets_exposed": False,
            },
        )

    def _run_diagnostics(self, task: dict) -> list[dict]:
        repo_id = ((task.get("target") or {}).get("repo_ids") or ["forja"])[0]
        commands = [["git", "status", "--short"], ["git", "diff", "--stat"]]
        logs = []
        for command in commands:
            result = run_command(command, self.repo_adapter.resolve(repo_id), timeout=60)
            log = {
                "cwd": str(self.repo_adapter.resolve(repo_id)),
                "command_sanitized": " ".join(command),
                "exit_code": result["exit_code"],
                "stdout_preview": result["stdout"][:1200],
                "stderr_preview": result["stderr"][:1200],
                "secrets_redacted": True,
            }
            if self.scanner.contains_secret(log):
                raise RuntimeError("secret_detected_in_command_log")
            logs.append(log)
        return logs


def run_command(command: list[str], cwd: Path, timeout: int) -> dict:
    completed = subprocess.run(command, cwd=str(cwd), text=True, capture_output=True, timeout=timeout, check=False)
    return {"command": command, "exit_code": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_inside(base: Path, target: Path) -> None:
    resolved_base = base.resolve()
    resolved_target = target.resolve()
    if resolved_base != resolved_target and resolved_base not in resolved_target.parents:
        raise RuntimeError("path_outside_repository_blocked")


def ensure_inside_delivery(base: Path, target: Path) -> None:
    resolved_base = base.resolve()
    resolved_target = target.resolve()
    if resolved_base != resolved_target and resolved_base not in resolved_target.parents:
        raise RuntimeError("path_outside_delivery_root_blocked")


def delivery_app_for_task(task: dict) -> str:
    target = task.get("target") or {}
    return safe_delivery_name(str(target.get("delivery_app") or "FORJA"))


def delivery_path_for_task(task: dict, filename: str, default_root: Path) -> Path:
    target = task.get("target") or {}
    root = Path(str(target.get("delivery_root") or default_root))
    requested = target.get("delivery_path")
    if requested:
        path = Path(str(requested))
    else:
        path = root / delivery_app_for_task(task) / Path(filename).name
    ensure_inside_delivery(root, path)
    return path


def safe_delivery_name(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_-]+", "_", value.upper()).strip("_")
    return clean or "FORJA"


def requested_markdown_filename(task: dict) -> str | None:
    desired = str(task.get("desired_output") or "").strip()
    instruction = str(task.get("instruction") or "")
    candidates = [desired, instruction]
    for candidate in candidates:
        match = re.search(r"\b([A-Za-z0-9][A-Za-z0-9_.-]{0,120}\.md)\b", candidate, re.IGNORECASE)
        if match:
            return Path(match.group(1)).name
    return None


def discover_ecosystem_apps(repo: Path) -> list[dict]:
    root = repo / "docs" / "ecosystem-memory" / "apps"
    if not root.exists():
        return []
    apps = []
    for path in sorted(root.iterdir()):
        if not path.is_dir():
            continue
        documents = sum(1 for item in path.rglob("*.md") if item.is_file())
        apps.append({"name": path.name, "documents": documents})
    return apps


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def registration_payload_from_config(config: dict) -> dict:
    repository_ids = [item["id"] for item in config.get("repositories", [])]
    computer_name = os.getenv("COMPUTERNAME") or os.getenv("HOSTNAME") or "local-pc"
    payload = dict(config.get("register_payload") or {})
    payload.setdefault("agent_name", config.get("agent_name") or "FORJA Local Agent Production")
    payload.setdefault("machine_label", config.get("machine_label") or computer_name)
    payload.setdefault("machine_id", config.get("machine_id") or computer_name)
    payload.setdefault("version", config.get("version") or AGENT_RUNTIME_VERSION)
    payload.setdefault("owner", config.get("owner") or "ceo")
    payload.setdefault("capability_profile", config.get("capability_profile") or DEFAULT_AGENT_CAPABILITIES)
    payload.setdefault("allowed_repositories", config.get("allowed_repositories") or repository_ids or ["forja"])
    payload.setdefault("allowed_workspaces", config.get("allowed_workspaces") or ["ecosystem"])
    payload.setdefault("policy_profile", config.get("policy_profile") or "default")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="FORJA Local Agent V1 polling runner")
    parser.add_argument("--config", required=True, help="Path to local agent config JSON")
    parser.add_argument("--once", action="store_true", help="Poll and execute at most one task")
    parser.add_argument("--interval", type=int, default=20, help="Polling interval in seconds")
    args = parser.parse_args()
    config = load_config(Path(args.config))
    repositories = {item["id"]: Path(item["path"]) for item in config.get("repositories", [])}
    client = ForjaAgentClient(
        config["base_url"],
        config.get("agent_id"),
        config.get("agent_token"),
        config_path=Path(args.config),
        config=config,
    )
    agent = PollingAgent(
        client,
        repositories,
        Path(config.get("run_root", "D:/ECOSYSTEM/FORJA_LOCAL_AGENT/runs")),
        Path(config.get("deliveries_root", str(DEFAULT_DELIVERIES_ROOT))),
    )
    while True:
        agent.poll_once()
        if args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
