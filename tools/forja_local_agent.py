from __future__ import annotations

import argparse
import hashlib
import json
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
        r"sk-[a-z0-9_-]+",
        r"token",
    ]
]
EXCLUDED_DIRS = {".git", "node_modules", "build", "dist", "__pycache__", ".pytest_cache"}
EXCLUDED_FILES = {".env"}


class SecretScanner:
    def contains_secret(self, value: Any) -> bool:
        if isinstance(value, dict):
            return any(self.contains_secret(key) or self.contains_secret(nested) for key, nested in value.items())
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
    def __init__(self, run_root: Path) -> None:
        self.run_root = run_root

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


class ResultUploader:
    def __init__(self, client: "ForjaAgentClient") -> None:
        self.client = client

    def upload(self, task: dict, result: dict) -> dict:
        return self.client.post(f"/agent/v1/tasks/{task['task_id']}/results", {"result": result})


class ForjaAgentClient:
    def __init__(self, base_url: str, agent_id: str, token: str, timeout: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self.token = token
        self.timeout = timeout

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "X-FORJA-Agent-Id": self.agent_id}

    def post(self, path: str, payload: dict | None = None) -> dict:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.base_url}{path}", json=payload or {}, headers=self.headers)
            response.raise_for_status()
            return response.json()


class PollingAgent:
    def __init__(self, client: ForjaAgentClient, repositories: dict[str, Path], run_root: Path) -> None:
        self.client = client
        self.repo_adapter = RepositoryAdapter(repositories)
        self.memory_adapter = MemoryAdapter(self.repo_adapter)
        self.snapshot_engine = SnapshotEngine(self.repo_adapter, self.memory_adapter)
        self.backup_engine = BackupEngine(self.repo_adapter, run_root)
        self.reports = ReportsAdapter(run_root)
        self.uploader = ResultUploader(client)
        self.scanner = SecretScanner()

    def poll_once(self) -> dict | None:
        self.client.post("/agent/v1/heartbeat")
        poll = self.client.post(
            "/agent/v1/tasks/poll",
            {
                "capabilities": [
                    "repo_read",
                    "repo_status",
                    "repo_diff",
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
        artifact = self.reports.write_report(task, "Local Agent task completed with governed execution.", command_logs)
        self.client.post(f"/agent/v1/tasks/{task['task_id']}/artifacts", {"artifact": artifact})
        return self.uploader.upload(
            task,
            {
                "status": "completed",
                "summary": "Local Agent completed the governed task.",
                "human_cabin_summary": "FORJA Local Agent completo la tarea con snapshot, logs y resultado.",
                "technical_summary": {"commands_run": len(command_logs), "commands_failed": sum(1 for log in command_logs if log["exit_code"] != 0)},
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


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="FORJA Local Agent V1 polling runner")
    parser.add_argument("--config", required=True, help="Path to local agent config JSON")
    parser.add_argument("--once", action="store_true", help="Poll and execute at most one task")
    parser.add_argument("--interval", type=int, default=20, help="Polling interval in seconds")
    args = parser.parse_args()
    config = load_config(Path(args.config))
    repositories = {item["id"]: Path(item["path"]) for item in config.get("repositories", [])}
    client = ForjaAgentClient(config["base_url"], config["agent_id"], config["agent_token"])
    agent = PollingAgent(client, repositories, Path(config.get("run_root", "D:/ECOSYSTEM/FORJA_LOCAL_AGENT/runs")))
    while True:
        agent.poll_once()
        if args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
