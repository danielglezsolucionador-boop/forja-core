from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
from threading import RLock
import uuid
from typing import Any

from fastapi import HTTPException

from app.core.audit import append_audit_event, utc_now
from app.core.config import settings
from app.core.storage import store
from app.services.ecosystem_memory_service import ecosystem_memory_service


DEFAULT_AGENT_CAPABILITIES = [
    "repo_read",
    "repo_status",
    "repo_diff",
    "repo_branch_create",
    "repo_edit_controlled",
    "repo_commit_prepare",
    "memory_read",
    "reports_read",
    "reports_generate",
    "deliveries_read",
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
READ_TYPES = {"read", "diagnosis", "build", "test", "audit"}
MUTATING_TYPES = {"report_generation", "controlled_edit", "commit_prepare", "commit_execute", "push", "deploy", "rollback"}
CRITICAL_TYPES = {"commit_execute", "push", "deploy", "rollback"}
LEASE_MINUTES = 10
AGENT_ONLINE_SECONDS = 90
AGENT_OFFLINE_SECONDS = 300
AGENT_REGISTRY_TABLE = "local_agent_agents"
AGENT_TASKS_TABLE = "local_agent_tasks"
SECRET_MARKERS = [
    "api_key",
    "apikey",
    "authorization",
    "bearer ",
    "credential",
    "openrouter_api_key",
    "password",
    "private_key",
    "secret",
    "sk-",
    "token",
]
SECRET_TEXT_PATTERNS = [
    re.compile(r"(?<![a-z0-9])sk-[a-z0-9_-]{16,}", re.IGNORECASE),
]


def _postgres_url() -> str:
    database_url = settings.database_url.strip()
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return database_url


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_to_db(value: str | None) -> datetime | None:
    return _parse_datetime(value)


class LocalAgentPersistentListStore:
    def __init__(self, name: str, table_name: str, id_field: str) -> None:
        self._json_store = store(name)
        self._table_name = table_name
        self._id_field = id_field
        self._lock = RLock()
        self._schema_ready = False

    def read(self, default: Any) -> Any:
        if not settings.database_enabled:
            return self._json_store.read(default)
        try:
            return self._read_database(default)
        except Exception as exc:
            if settings.is_local:
                return self._json_store.read(default)
            raise HTTPException(
                status_code=503,
                detail=f"local_agent_persistence_unavailable:{exc.__class__.__name__}",
            ) from exc

    def write(self, payload: Any) -> None:
        if not settings.database_enabled:
            self._json_store.write(payload)
            return
        try:
            self._write_database(payload)
        except Exception as exc:
            if settings.is_local:
                self._json_store.write(payload)
                return
            raise HTTPException(
                status_code=503,
                detail=f"local_agent_persistence_unavailable:{exc.__class__.__name__}",
            ) from exc

    def update(self, default: Any, mutator):
        with self._lock:
            payload = self.read(default)
            result = mutator(payload)
            self.write(payload)
            return result

    def _connect(self):
        import psycopg2

        kwargs = {}
        if settings.database_ssl:
            kwargs["sslmode"] = "require"
        return psycopg2.connect(_postgres_url(), **kwargs)

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        if self._table_name == AGENT_REGISTRY_TABLE:
            statement = f"""
                CREATE TABLE IF NOT EXISTS {AGENT_REGISTRY_TABLE} (
                    agent_id VARCHAR(80) PRIMARY KEY,
                    agent_name VARCHAR(160) NOT NULL,
                    machine_label VARCHAR(160) NOT NULL,
                    machine_id VARCHAR(160),
                    version VARCHAR(80),
                    owner VARCHAR(120) NOT NULL,
                    status VARCHAR(40) NOT NULL,
                    last_seen_at TIMESTAMPTZ,
                    token_hash VARCHAR(128) NOT NULL,
                    capabilities JSONB NOT NULL DEFAULT '[]'::jsonb,
                    payload JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    revoked_at TIMESTAMPTZ
                )
            """
        else:
            statement = f"""
                CREATE TABLE IF NOT EXISTS {AGENT_TASKS_TABLE} (
                    task_id VARCHAR(80) PRIMARY KEY,
                    agent_id VARCHAR(80),
                    status VARCHAR(40) NOT NULL,
                    task_type VARCHAR(80) NOT NULL,
                    payload JSONB NOT NULL,
                    result JSONB,
                    error TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    completed_at TIMESTAMPTZ
                )
            """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement)
                if self._table_name == AGENT_REGISTRY_TABLE:
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS ix_{AGENT_REGISTRY_TABLE}_status ON {AGENT_REGISTRY_TABLE} (status)"
                    )
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS ix_{AGENT_REGISTRY_TABLE}_last_seen_at ON {AGENT_REGISTRY_TABLE} (last_seen_at)"
                    )
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS ix_{AGENT_REGISTRY_TABLE}_machine_id ON {AGENT_REGISTRY_TABLE} (machine_id)"
                    )
                else:
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS ix_{AGENT_TASKS_TABLE}_status ON {AGENT_TASKS_TABLE} (status)"
                    )
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS ix_{AGENT_TASKS_TABLE}_agent_id ON {AGENT_TASKS_TABLE} (agent_id)"
                    )
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS ix_{AGENT_TASKS_TABLE}_updated_at ON {AGENT_TASKS_TABLE} (updated_at)"
                    )
            connection.commit()
        self._schema_ready = True

    def _read_database(self, default: Any) -> Any:
        self._ensure_schema()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT payload
                    FROM {self._table_name}
                    ORDER BY created_at ASC
                    """
                )
                rows = cursor.fetchall()
        if not rows:
            return default
        return [row[0] for row in rows]

    def _write_database(self, payload: list[dict]) -> None:
        from psycopg2.extras import Json

        self._ensure_schema()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for item in payload:
                    if self._table_name == AGENT_REGISTRY_TABLE:
                        cursor.execute(
                            f"""
                            INSERT INTO {AGENT_REGISTRY_TABLE} (
                                agent_id, agent_name, machine_label, machine_id, version,
                                owner, status, last_seen_at, token_hash, capabilities,
                                payload, created_at, updated_at, revoked_at
                            )
                            VALUES (
                                %(agent_id)s, %(agent_name)s, %(machine_label)s,
                                %(machine_id)s, %(version)s, %(owner)s, %(status)s,
                                %(last_seen_at)s, %(token_hash)s, %(capabilities)s,
                                %(payload)s, %(created_at)s, %(updated_at)s,
                                %(revoked_at)s
                            )
                            ON CONFLICT(agent_id) DO UPDATE SET
                                agent_name = excluded.agent_name,
                                machine_label = excluded.machine_label,
                                machine_id = excluded.machine_id,
                                version = excluded.version,
                                owner = excluded.owner,
                                status = excluded.status,
                                last_seen_at = excluded.last_seen_at,
                                token_hash = excluded.token_hash,
                                capabilities = excluded.capabilities,
                                payload = excluded.payload,
                                updated_at = excluded.updated_at,
                                revoked_at = excluded.revoked_at
                            """,
                            {
                                "agent_id": item["agent_id"],
                                "agent_name": item["agent_name"],
                                "machine_label": item["machine_label"],
                                "machine_id": item.get("machine_id"),
                                "version": item.get("version"),
                                "owner": item.get("owner", "ceo"),
                                "status": item.get("status", "registered"),
                                "last_seen_at": _iso_to_db(item.get("last_seen_at")),
                                "token_hash": item["token_hash"],
                                "capabilities": Json(item.get("capability_profile") or []),
                                "payload": Json(item),
                                "created_at": _iso_to_db(item.get("created_at")) or datetime.now(timezone.utc),
                                "updated_at": _iso_to_db(item.get("updated_at")) or datetime.now(timezone.utc),
                                "revoked_at": _iso_to_db(item.get("revoked_at")),
                            },
                        )
                    else:
                        completed = item.get("completed_at")
                        if not completed and item.get("status") in {"completed", "failed", "blocked", "cancelled", "rolled_back"}:
                            completed = item.get("updated_at")
                        result = item.get("result")
                        error = None
                        if isinstance(result, dict):
                            error = result.get("error") or result.get("error_message")
                        cursor.execute(
                            f"""
                            INSERT INTO {AGENT_TASKS_TABLE} (
                                task_id, agent_id, status, task_type, payload, result,
                                error, created_at, updated_at, completed_at
                            )
                            VALUES (
                                %(task_id)s, %(agent_id)s, %(status)s, %(task_type)s,
                                %(payload)s, %(result)s, %(error)s, %(created_at)s,
                                %(updated_at)s, %(completed_at)s
                            )
                            ON CONFLICT(task_id) DO UPDATE SET
                                agent_id = excluded.agent_id,
                                status = excluded.status,
                                task_type = excluded.task_type,
                                payload = excluded.payload,
                                result = excluded.result,
                                error = excluded.error,
                                updated_at = excluded.updated_at,
                                completed_at = excluded.completed_at
                            """,
                            {
                                "task_id": item["task_id"],
                                "agent_id": item.get("assigned_agent_id"),
                                "status": item.get("status", "queued"),
                                "task_type": item.get("task_type", "diagnosis"),
                                "payload": Json(item),
                                "result": Json(result) if result is not None else None,
                                "error": error,
                                "created_at": _iso_to_db(item.get("created_at")) or datetime.now(timezone.utc),
                                "updated_at": _iso_to_db(item.get("updated_at")) or datetime.now(timezone.utc),
                                "completed_at": _iso_to_db(completed),
                            },
                        )
            connection.commit()


class LocalAgentPolicyEngine:
    def classify(self, payload: dict) -> dict:
        instruction = str(payload.get("instruction", "")).lower()
        task_type = self._task_type(instruction)
        risk = self._risk_level(task_type)
        mutating = task_type in MUTATING_TYPES
        critical = task_type in CRITICAL_TYPES
        capabilities = self._capabilities(task_type)
        return {
            "task_type": task_type,
            "risk_level": risk,
            "capabilities_required": capabilities,
            "policy": {
                "requires_snapshot": True,
                "requires_backup": mutating,
                "requires_branch": task_type in {"controlled_edit", "commit_prepare", "commit_execute"},
                "requires_human_approval": task_type in {"controlled_edit", "commit_prepare", "report_generation"} and mutating,
                "requires_critical_approval": critical,
                "requires_rollback_plan": mutating,
                "secrets_allowed": False,
                "push_automatic": False,
                "deploy_automatic": False,
                "allowed_commands": self._allowed_commands(task_type),
            },
        }

    def evaluate_agent(self, task: dict, agent: dict, poll_payload: dict | None = None) -> dict:
        agent_capabilities = set(agent.get("capability_profile") or [])
        poll_capabilities = set((poll_payload or {}).get("capabilities") or agent_capabilities)
        capabilities = agent_capabilities | poll_capabilities
        required = set(task.get("capabilities_required") or [])
        missing = sorted(required - capabilities)
        allowed_repositories = set(agent.get("allowed_repositories") or [])
        requested_repositories = set((task.get("target") or {}).get("repo_ids") or [])
        repo_blocked = bool(requested_repositories and allowed_repositories and not requested_repositories.issubset(allowed_repositories))
        if missing or repo_blocked:
            return {
                "allowed": False,
                "reason": "missing_capabilities" if missing else "repository_not_allowed",
                "missing_capabilities": missing,
                "repo_blocked": repo_blocked,
            }
        return {"allowed": True, "reason": "policy_allowed"}

    def contains_secret(self, value: Any) -> bool:
        if isinstance(value, dict):
            for key, nested in value.items():
                key_text = str(key).lower()
                if key_text in {"secrets_found", "secrets_exposed"}:
                    if nested is True:
                        return True
                    continue
                if key_text in {"secrets_scanned", "secrets_redacted", "excluded"}:
                    continue
                if any(marker in key_text for marker in SECRET_MARKERS) and nested not in {False, None, "", "redacted"}:
                    return True
                if self.contains_secret(nested):
                    return True
            return False
        if isinstance(value, list):
            return any(self.contains_secret(item) for item in value)
        text = str(value).lower()
        simple_markers = [marker for marker in SECRET_MARKERS if marker != "sk-"]
        return any(marker in text for marker in simple_markers) or any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)

    def _task_type(self, instruction: str) -> str:
        if "deploy" in instruction or "desplieg" in instruction:
            return "deploy"
        if "push" in instruction:
            return "push"
        if "rollback" in instruction or "revert" in instruction:
            return "rollback"
        if "commit" in instruction and any(word in instruction for word in ["ejecut", "crear", "hacer"]):
            return "commit_execute"
        if "commit" in instruction:
            return "commit_prepare"
        if any(word in instruction for word in ["implementar", "editar", "modificar", "corregir", "fix", "cambiar codigo", "código", "codigo"]):
            return "controlled_edit"
        if "build" in instruction or "compilar" in instruction:
            return "build"
        if "test" in instruction or "prueba" in instruction:
            return "test"
        if "auditar" in instruction or "auditoria" in instruction or "diagnost" in instruction:
            return "audit"
        if "reporte" in instruction or "report" in instruction or "inventario" in instruction or ".md" in instruction or "guarda" in instruction or "guardar" in instruction:
            return "report_generation"
        if "leer" in instruction or "listar" in instruction:
            return "read"
        return "diagnosis"

    def _risk_level(self, task_type: str) -> str:
        if task_type in CRITICAL_TYPES:
            return "critical"
        if task_type in {"controlled_edit", "commit_prepare", "report_generation"}:
            return "high"
        if task_type in {"build", "test", "audit", "diagnosis"}:
            return "medium"
        return "low"

    def _capabilities(self, task_type: str) -> list[str]:
        base = ["snapshot_create", "memory_read", "artifact_upload"]
        mapping = {
            "read": ["repo_read", "reports_read", "deliveries_read"],
            "diagnosis": ["repo_status", "repo_diff", "logs_read"],
            "audit": ["repo_status", "repo_diff", "audit_run", "reports_generate"],
            "build": ["repo_read", "build_run", "logs_read"],
            "test": ["repo_read", "tests_run", "logs_read"],
            "report_generation": ["reports_generate", "backup_create", "rollback_plan"],
            "controlled_edit": ["repo_edit_controlled", "repo_branch_create", "backup_create", "rollback_plan"],
            "commit_prepare": ["repo_commit_prepare", "backup_create", "rollback_plan"],
            "commit_execute": ["repo_commit_prepare", "backup_create", "rollback_plan"],
            "push": ["repo_commit_prepare", "backup_create", "rollback_plan"],
            "deploy": ["repo_status", "build_run", "tests_run", "backup_create", "rollback_plan"],
            "rollback": ["backup_create", "rollback_plan"],
        }
        return sorted(set(base + mapping.get(task_type, [])))

    def _allowed_commands(self, task_type: str) -> list[str]:
        commands = ["git status", "git diff", "rg", "python -m pytest", "npm run build"]
        if task_type in {"controlled_edit", "commit_prepare"}:
            commands.extend(["git checkout -b", "git add", "git commit --dry-run"])
        if task_type in CRITICAL_TYPES:
            commands.append("requires_critical_human_approval")
        return commands


class LocalAgentMemoryAdapter:
    def context(self) -> dict:
        snapshot = ecosystem_memory_service.snapshot()
        return {
            "connected": snapshot.get("connected"),
            "primary_source": snapshot.get("primary_source", {}).get("path"),
            "additional_sources": [source.get("path") for source in snapshot.get("additional_sources", []) if source.get("exists")],
            "registered_apps": snapshot.get("registered_apps", []),
            "active_apps": snapshot.get("active_apps", []),
            "priorities": snapshot.get("priorities", []),
            "blockers": snapshot.get("blockers", []),
            "construction": snapshot.get("construction", []),
        }


class LocalAgentRepositoryAdapter:
    def context(self, task: dict) -> dict:
        target = task.get("target") or {}
        return {
            "repo_ids": target.get("repo_ids") or ["forja"],
            "paths": target.get("paths") or [],
            "protected_branches": ["main"],
            "allowed_operations": task.get("capabilities_required", []),
        }


class LocalAgentReportsAdapter:
    def result_report(self, task: dict, result: dict) -> dict:
        return {
            "name": f"{task['task_id']}_RESULT_SUMMARY.md",
            "kind": "local_agent_result",
            "summary": result.get("summary") or result.get("human_cabin_summary") or "Local Agent task result recorded.",
            "visible_in_human_cabin": True,
        }


class LocalAgentService:
    def __init__(self) -> None:
        self._agents = LocalAgentPersistentListStore("local_agent_registry", AGENT_REGISTRY_TABLE, "agent_id")
        self._tasks = LocalAgentPersistentListStore("local_agent_tasks", AGENT_TASKS_TABLE, "task_id")
        self._policy = LocalAgentPolicyEngine()
        self._memory = LocalAgentMemoryAdapter()
        self._repos = LocalAgentRepositoryAdapter()
        self._reports = LocalAgentReportsAdapter()

    def register_agent(self, payload: dict, registration_token: str | None = None) -> dict:
        self._authorize_registration(registration_token)
        now = utc_now()
        agent_id = f"agent-{uuid.uuid4()}"
        secret = secrets.token_urlsafe(32)
        token = f"forja_agent_v1_{agent_id}.{secret}"
        record = {
            "agent_id": agent_id,
            "agent_name": payload["agent_name"],
            "machine_label": payload["machine_label"],
            "machine_id": payload.get("machine_id"),
            "version": payload.get("version"),
            "owner": payload.get("owner", "ceo"),
            "status": "registered",
            "last_seen_at": None,
            "token_hash": self._hash_token(token),
            "capability_profile": payload.get("capability_profile") or DEFAULT_AGENT_CAPABILITIES,
            "allowed_repositories": payload.get("allowed_repositories") or ["forja"],
            "allowed_workspaces": payload.get("allowed_workspaces") or ["ecosystem"],
            "policy_profile": payload.get("policy_profile", "default"),
            "created_at": now,
            "updated_at": now,
            "revoked_at": None,
        }
        self._agents.update([], lambda agents: agents.append(record))
        append_audit_event("local_agent.registered", payload.get("owner", "ceo"), {"agent_id": agent_id, "machine_label": record["machine_label"]})
        return {**self._public_agent(record), "agent_token": token}

    def _authorize_registration(self, registration_token: str | None) -> None:
        if settings.is_local:
            return
        configured_token = settings.local_agent_registration_token.strip()
        if configured_token:
            if not registration_token or not secrets.compare_digest(registration_token, configured_token):
                raise HTTPException(status_code=403, detail="invalid_agent_registration_token")
            return
        if self._agents.read([]):
            raise HTTPException(status_code=403, detail="agent_registration_locked")

    def list_agents(self) -> list[dict]:
        return [self._public_agent(agent) for agent in self._agents.read([])]

    def authenticate_agent(self, agent_id: str, token: str) -> dict:
        for agent in self._agents.read([]):
            if agent.get("agent_id") != agent_id:
                continue
            if agent.get("status") == "revoked":
                raise HTTPException(status_code=403, detail="agent_revoked")
            if agent.get("token_hash") != self._hash_token(token):
                raise HTTPException(status_code=401, detail="invalid_agent_token")
            return agent
        raise HTTPException(status_code=401, detail="agent_not_registered")

    def heartbeat(self, agent: dict) -> dict:
        now = utc_now()

        def mutate(agents: list[dict]) -> dict:
            for record in agents:
                if record.get("agent_id") == agent["agent_id"]:
                    record["status"] = "online"
                    record["last_seen_at"] = now
                    record["updated_at"] = now
                    return self._public_agent(record)
            raise HTTPException(status_code=404, detail="agent_not_found")

        result = self._agents.update([], mutate)
        append_audit_event("local_agent.heartbeat", agent["agent_id"], {"agent_id": agent["agent_id"]})
        return result

    def create_task(self, payload: dict) -> dict:
        now = utc_now()
        classification = self._policy.classify(payload)
        status = "awaiting_critical_approval" if classification["policy"]["requires_critical_approval"] else (
            "awaiting_human_approval" if classification["policy"]["requires_human_approval"] else "queued"
        )
        task = {
            "task_id": f"task-{uuid.uuid4()}",
            "title": payload.get("title") or self._title_from_instruction(payload["instruction"]),
            "instruction": payload["instruction"],
            "source": payload.get("source", "human_cabin"),
            "requested_by": payload.get("requested_by", "ceo"),
            "created_at": now,
            "updated_at": now,
            "status": status,
            "priority": payload.get("priority", "normal"),
            "risk_level": classification["risk_level"],
            "task_type": classification["task_type"],
            "capabilities_required": classification["capabilities_required"],
            "target": payload.get("target") or {"workspace_id": "ecosystem", "repo_ids": ["forja"], "paths": []},
            "policy": classification["policy"],
            "assigned_agent_id": None,
            "lease": None,
            "approvals": [],
            "history": [],
            "snapshots": [],
            "backups": [],
            "rollback": None,
            "command_logs": [],
            "artifacts": [],
            "result": None,
            "error": None,
            "completed_at": None,
            "memory_context": self._memory.context(),
            "repository_context": None,
        }
        task["repository_context"] = self._repos.context(task)
        self._append_event(task, "task.created", {"status": status, "task_type": task["task_type"]}, task["risk_level"])
        self._tasks.update([], lambda tasks: tasks.append(task))
        append_audit_event("local_agent.task_created", task["requested_by"], {"task_id": task["task_id"], "status": status, "task_type": task["task_type"]}, risk=task["risk_level"])
        return task

    def list_tasks(self, limit: int = 100) -> list[dict]:
        return self._tasks.read([])[-limit:]

    def get_task(self, task_id: str) -> dict | None:
        return next((task for task in self._tasks.read([]) if task.get("task_id") == task_id), None)

    def approve_task(self, task_id: str, payload: dict, critical: bool = False) -> dict:
        now = utc_now()

        def mutate(tasks: list[dict]) -> dict:
            task = self._find_task(tasks, task_id)
            if critical:
                if not task["policy"].get("requires_critical_approval"):
                    raise HTTPException(status_code=409, detail="critical_approval_not_required")
                approval_type = "critical"
            else:
                if task["policy"].get("requires_critical_approval") or task["status"] == "awaiting_critical_approval":
                    raise HTTPException(status_code=409, detail="critical_approval_required")
                if task["status"] not in {"awaiting_human_approval", "awaiting_critical_approval"}:
                    raise HTTPException(status_code=409, detail="task_not_waiting_for_approval")
                approval_type = "human"
            approval = {
                "approval_id": f"approval-{uuid.uuid4()}",
                "task_id": task_id,
                "type": approval_type,
                "approved_by": payload.get("approved_by", "ceo"),
                "reason": payload.get("reason", ""),
                "action": payload.get("action") or task["task_type"],
                "exact_target": payload.get("exact_target", {}),
                "approved_at": now,
            }
            task["approvals"].append(approval)
            task["status"] = "queued"
            task["updated_at"] = now
            self._append_event(task, f"task.{approval_type}_approval.granted", approval, task["risk_level"])
            return task

        result = self._tasks.update([], mutate)
        append_audit_event("local_agent.task_approved", payload.get("approved_by", "ceo"), {"task_id": task_id, "critical": critical}, risk=result["risk_level"])
        return result

    def poll_tasks(self, agent: dict, payload: dict) -> dict:
        self.heartbeat(agent)
        tasks = self._tasks.read([])
        candidates: list[dict] = []
        for task in reversed(tasks):
            if task.get("status") != "queued":
                continue
            decision = self._policy.evaluate_agent(task, agent, payload)
            if decision["allowed"]:
                candidates.append(task)
            else:
                self._append_event(task, "task.poll.skipped", decision, task["risk_level"])
        return {"agent_id": agent["agent_id"], "tasks": candidates[: payload.get("max_tasks", 1)]}

    def lease_task(self, task_id: str, agent: dict) -> dict:
        now = datetime.now(timezone.utc)
        lease = {
            "lease_id": f"lease-{uuid.uuid4()}",
            "task_id": task_id,
            "agent_id": agent["agent_id"],
            "leased_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=LEASE_MINUTES)).isoformat(),
            "heartbeat_at": now.isoformat(),
            "renewal_count": 0,
        }

        def mutate(tasks: list[dict]) -> dict:
            task = self._find_task(tasks, task_id)
            if task["status"] != "queued":
                raise HTTPException(status_code=409, detail="task_not_queued")
            decision = self._policy.evaluate_agent(task, agent)
            if not decision["allowed"]:
                raise HTTPException(status_code=403, detail=decision["reason"])
            task["status"] = "leased"
            task["assigned_agent_id"] = agent["agent_id"]
            task["lease"] = lease
            task["updated_at"] = utc_now()
            self._append_event(task, "task.leased", lease, task["risk_level"])
            return {"task": task, **lease}

        result = self._tasks.update([], mutate)
        append_audit_event("local_agent.task_leased", agent["agent_id"], {"task_id": task_id, "lease_id": lease["lease_id"]}, risk=result["task"]["risk_level"])
        return result

    def task_heartbeat(self, task_id: str, agent: dict) -> dict:
        now = datetime.now(timezone.utc).isoformat()

        def mutate(tasks: list[dict]) -> dict:
            task = self._agent_task(tasks, task_id, agent)
            if not task.get("lease"):
                raise HTTPException(status_code=409, detail="task_not_leased")
            task["lease"]["heartbeat_at"] = now
            task["lease"]["renewal_count"] = int(task["lease"].get("renewal_count", 0)) + 1
            task["updated_at"] = utc_now()
            self._append_event(task, "task.heartbeat", {"heartbeat_at": now}, "low")
            return task

        return self._tasks.update([], mutate)

    def record_snapshot(self, task_id: str, agent: dict, snapshot: dict) -> dict:
        self._reject_secret_payload(snapshot)

        def mutate(tasks: list[dict]) -> dict:
            task = self._agent_task(tasks, task_id, agent)
            snapshot_record = {"snapshot_id": f"snapshot-{uuid.uuid4()}", "created_at": utc_now(), **snapshot}
            task["snapshots"].append(snapshot_record)
            task["status"] = "backing_up" if task["policy"].get("requires_backup") else "running"
            task["updated_at"] = utc_now()
            self._append_event(task, "task.snapshot.created", {"snapshot_id": snapshot_record["snapshot_id"]}, "low")
            return task

        return self._tasks.update([], mutate)

    def record_backup(self, task_id: str, agent: dict, backup: dict) -> dict:
        self._reject_secret_payload(backup)

        def mutate(tasks: list[dict]) -> dict:
            task = self._agent_task(tasks, task_id, agent)
            if not task["policy"].get("requires_backup"):
                raise HTTPException(status_code=409, detail="backup_not_required")
            backup_record = {"backup_id": f"backup-{uuid.uuid4()}", "created_at": utc_now(), **backup}
            if not backup_record.get("validated", False):
                raise HTTPException(status_code=409, detail="backup_not_validated")
            if backup_record.get("secrets_found"):
                raise HTTPException(status_code=409, detail="backup_contains_secret")
            task["backups"].append(backup_record)
            task["status"] = "preparing_workspace"
            task["updated_at"] = utc_now()
            self._append_event(task, "task.backup.created", {"backup_id": backup_record["backup_id"]}, task["risk_level"])
            return task

        return self._tasks.update([], mutate)

    def record_rollback(self, task_id: str, agent: dict, rollback: dict) -> dict:
        self._reject_secret_payload(rollback)

        def mutate(tasks: list[dict]) -> dict:
            task = self._agent_task(tasks, task_id, agent)
            record = {"rollback_id": f"rollback-{uuid.uuid4()}", "created_at": utc_now(), **rollback}
            task["rollback"] = record
            task["updated_at"] = utc_now()
            self._append_event(task, "task.rollback.registered", {"rollback_id": record["rollback_id"]}, task["risk_level"])
            return task

        return self._tasks.update([], mutate)

    def record_event(self, task_id: str, agent: dict, event: dict) -> dict:
        self._reject_secret_payload(event)

        def mutate(tasks: list[dict]) -> dict:
            task = self._agent_task(tasks, task_id, agent)
            self._append_event(task, event["event_type"], event.get("payload", {}), event.get("risk", "low"), event.get("idempotency_key"))
            task["updated_at"] = utc_now()
            return task

        return self._tasks.update([], mutate)

    def record_log(self, task_id: str, agent: dict, command_log: dict) -> dict:
        self._reject_secret_payload(command_log)

        def mutate(tasks: list[dict]) -> dict:
            task = self._agent_task(tasks, task_id, agent)
            task["command_logs"].append({"command_log_id": f"cmdlog-{uuid.uuid4()}", "created_at": utc_now(), **command_log})
            task["status"] = "running"
            task["updated_at"] = utc_now()
            self._append_event(task, "task.execution.log", {"command": command_log.get("command_sanitized")}, task["risk_level"])
            return task

        return self._tasks.update([], mutate)

    def record_artifact(self, task_id: str, agent: dict, artifact: dict) -> dict:
        self._reject_secret_payload(artifact)

        def mutate(tasks: list[dict]) -> dict:
            task = self._agent_task(tasks, task_id, agent)
            if artifact.get("secrets_found"):
                raise HTTPException(status_code=409, detail="artifact_contains_secret")
            task["artifacts"].append({"artifact_id": f"artifact-{uuid.uuid4()}", "created_at": utc_now(), **artifact})
            task["updated_at"] = utc_now()
            self._append_event(task, "task.artifact.uploaded", {"name": artifact.get("name")}, task["risk_level"])
            return task

        return self._tasks.update([], mutate)

    def record_result(self, task_id: str, agent: dict, result: dict) -> dict:
        self._reject_secret_payload(result)

        def mutate(tasks: list[dict]) -> dict:
            task = self._agent_task(tasks, task_id, agent)
            self._validate_completion_gates(task, result)
            report = self._reports.result_report(task, result)
            final_result = {
                "result_id": f"result-{uuid.uuid4()}",
                "created_at": utc_now(),
                "secrets_exposed": False,
                "report": report,
                **result,
            }
            task["result"] = final_result
            task["status"] = result.get("status", "completed")
            if task["status"] not in {"completed", "failed", "blocked", "cancelled", "rolled_back"}:
                task["status"] = "completed"
            task["updated_at"] = utc_now()
            task["completed_at"] = task["updated_at"]
            if task["status"] == "failed":
                task["error"] = result.get("error") or result.get("error_message") or result.get("summary")
            self._append_event(task, "task.result.uploaded", {"result_id": final_result["result_id"], "status": task["status"]}, task["risk_level"])
            if task["status"] == "completed":
                self._append_event(task, "task.completed", {"result_id": final_result["result_id"]}, task["risk_level"])
            return task

        result_task = self._tasks.update([], mutate)
        append_audit_event("local_agent.task_result_uploaded", agent["agent_id"], {"task_id": task_id, "status": result_task["status"]}, risk=result_task["risk_level"])
        return result_task

    def dashboard(self) -> dict:
        agents = self.list_agents()
        tasks = self.list_tasks(limit=200)
        latest_results = [task for task in tasks if task.get("result")][-10:]
        critical = [task for task in tasks if task.get("status") == "awaiting_critical_approval"][-10:]
        rollbacks = [task for task in tasks if task.get("rollback")][-10:]
        online_agents = [agent for agent in agents if agent.get("status") == "online"]
        stale_agents = [agent for agent in agents if agent.get("status") == "stale"]
        offline_agents = [agent for agent in agents if agent.get("status") == "offline"]
        return {
            "agents": {
                "total": len(agents),
                "online": len(online_agents),
                "stale": len(stale_agents),
                "offline": len(offline_agents),
                "registered": sum(1 for agent in agents if agent.get("status") == "registered"),
                "last_heartbeat_at": max((agent.get("last_seen_at") or "" for agent in agents), default=None) or None,
                "status_message": (
                    "Agente local online."
                    if online_agents
                    else "No hay agente local conectado en este momento."
                ),
            },
            "tasks": {
                "total": len(tasks),
                "queued": sum(1 for task in tasks if task.get("status") == "queued"),
                "running": sum(1 for task in tasks if task.get("status") in {"leased", "snapshotting", "backing_up", "preparing_workspace", "running"}),
                "awaiting_approval": sum(1 for task in tasks if task.get("status") in {"awaiting_human_approval", "awaiting_critical_approval"}),
                "completed": sum(1 for task in tasks if task.get("status") == "completed"),
                "blocked": sum(1 for task in tasks if task.get("status") == "blocked"),
            },
            "latest_results": latest_results,
            "critical_approvals": critical,
            "deliveries": self._deliveries_from_tasks(latest_results),
            "rollbacks_available": rollbacks,
            "recent_activity": self._recent_activity(tasks),
        }

    def _deliveries_from_tasks(self, tasks: list[dict]) -> list[dict]:
        deliveries: list[dict] = []
        for task in tasks:
            result = task.get("result") or {}
            artifact = self._visible_artifact(task)
            target = task.get("target") or {}
            deliveries.append(
                {
                    "name": (artifact or {}).get("name") or result.get("report", {}).get("name") or task.get("title"),
                    "path": (artifact or {}).get("local_path") or target.get("delivery_path") or result.get("report", {}).get("local_path") or result.get("report", {}).get("name") or task.get("task_id"),
                    "status": task.get("status", "completed").upper(),
                    "task_id": task.get("task_id"),
                }
            )
        return deliveries[-10:]

    def _visible_artifact(self, task: dict) -> dict | None:
        artifacts = task.get("artifacts") or []
        target_path = (task.get("target") or {}).get("delivery_path")
        desired_output = task.get("desired_output")
        for artifact in artifacts:
            if not artifact.get("visible_in_human_cabin"):
                continue
            if artifact.get("local_path") == target_path or artifact.get("name") == desired_output:
                return artifact
        for artifact in reversed(artifacts):
            if artifact.get("visible_in_human_cabin"):
                return artifact
        return None

    def _recent_activity(self, tasks: list[dict]) -> list[dict]:
        events: list[dict] = []
        for task in tasks[-20:]:
            if task.get("history"):
                latest = task["history"][-1]
                events.append(
                    {
                        "time": latest.get("timestamp", task.get("updated_at")),
                        "event": latest.get("event_type"),
                        "app": "local_agent",
                        "result": task.get("title"),
                        "task_id": task.get("task_id"),
                    }
                )
        return list(reversed(events[-12:]))

    def _validate_completion_gates(self, task: dict, result: dict) -> None:
        if not task.get("snapshots"):
            raise HTTPException(status_code=409, detail="snapshot_required_before_result")
        if task["policy"].get("requires_backup") and not task.get("backups"):
            raise HTTPException(status_code=409, detail="backup_required_before_result")
        if task["policy"].get("requires_rollback_plan") and not task.get("rollback"):
            raise HTTPException(status_code=409, detail="rollback_required_before_result")
        if result.get("secrets_exposed") or result.get("secrets_found"):
            raise HTTPException(status_code=409, detail="result_contains_secret")

    def _reject_secret_payload(self, payload: Any) -> None:
        if self._policy.contains_secret(payload):
            raise HTTPException(status_code=409, detail="payload_contains_secret")

    def _agent_task(self, tasks: list[dict], task_id: str, agent: dict) -> dict:
        task = self._find_task(tasks, task_id)
        if task.get("assigned_agent_id") != agent["agent_id"]:
            raise HTTPException(status_code=403, detail="task_not_assigned_to_agent")
        return task

    def _find_task(self, tasks: list[dict], task_id: str) -> dict:
        for task in tasks:
            if task.get("task_id") == task_id:
                return task
        raise HTTPException(status_code=404, detail="local_agent_task_not_found")

    def _append_event(self, task: dict, event_type: str, payload: dict, risk: str = "low", idempotency_key: str | None = None) -> None:
        if idempotency_key and any(event.get("idempotency_key") == idempotency_key for event in task.get("history", [])):
            return
        task.setdefault("history", []).append(
            {
                "event_id": f"event-{uuid.uuid4()}",
                "task_id": task.get("task_id"),
                "event_type": event_type,
                "timestamp": utc_now(),
                "actor": "local_agent",
                "risk": risk,
                "payload": payload,
                "idempotency_key": idempotency_key,
            }
        )

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _public_agent(self, agent: dict) -> dict:
        public = {key: value for key, value in agent.items() if key != "token_hash"}
        if public.get("status") != "revoked":
            public["status"] = self._heartbeat_status(public.get("last_seen_at"), public.get("status", "registered"))
        return public

    def _title_from_instruction(self, instruction: str) -> str:
        clean = " ".join(instruction.split())
        return clean[:120] if clean else "FORJA Local Agent task"

    def _heartbeat_status(self, last_seen_at: str | None, current_status: str) -> str:
        if not last_seen_at:
            return "registered" if current_status == "registered" else "offline"
        parsed = _parse_datetime(last_seen_at)
        if parsed is None:
            return "offline"
        age = (datetime.now(timezone.utc) - parsed).total_seconds()
        if age <= AGENT_ONLINE_SECONDS:
            return "online"
        if age <= AGENT_OFFLINE_SECONDS:
            return "stale"
        return "offline"


local_agent_service = LocalAgentService()
