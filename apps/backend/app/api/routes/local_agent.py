from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from app.schemas.local_agent import (
    LocalAgentApprovalIn,
    LocalAgentArtifactIn,
    LocalAgentBackupIn,
    LocalAgentCommandLogIn,
    LocalAgentDashboard,
    LocalAgentEventIn,
    LocalAgentLeaseRecord,
    LocalAgentRecord,
    LocalAgentRegisterIn,
    LocalAgentResultIn,
    LocalAgentRollbackIn,
    LocalAgentSnapshotIn,
    LocalAgentTaskIn,
    LocalAgentTaskPollIn,
    LocalAgentTaskRecord,
)
from app.services.local_agent_service import local_agent_service


router = APIRouter(tags=["local-agent"])


def _agent_from_headers(x_forja_agent_id: str | None, authorization: str | None) -> dict:
    if not x_forja_agent_id:
        raise HTTPException(status_code=401, detail="missing_agent_id")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing_agent_token")
    return local_agent_service.authenticate_agent(x_forja_agent_id, authorization.split(" ", 1)[1].strip())


@router.post("/local-agent/agents", response_model=LocalAgentRecord)
def register_local_agent(
    payload: LocalAgentRegisterIn,
    x_forja_agent_registration_token: str | None = Header(default=None),
) -> dict:
    return local_agent_service.register_agent(
        payload.model_dump(),
        registration_token=x_forja_agent_registration_token,
    )


@router.get("/local-agent/agents", response_model=list[LocalAgentRecord])
def list_local_agents() -> list[dict]:
    return local_agent_service.list_agents()


@router.post("/local-agent/tasks", response_model=LocalAgentTaskRecord)
def create_local_agent_task(payload: LocalAgentTaskIn) -> dict:
    return local_agent_service.create_task(payload.model_dump())


@router.get("/local-agent/tasks", response_model=list[LocalAgentTaskRecord])
def list_local_agent_tasks(limit: int = 100) -> list[dict]:
    return local_agent_service.list_tasks(limit=limit)


@router.get("/local-agent/tasks/{task_id}", response_model=LocalAgentTaskRecord)
def get_local_agent_task(task_id: str) -> dict:
    task = local_agent_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="local_agent_task_not_found")
    return task


@router.post("/local-agent/tasks/{task_id}/approve", response_model=LocalAgentTaskRecord)
def approve_local_agent_task(task_id: str, payload: LocalAgentApprovalIn) -> dict:
    return local_agent_service.approve_task(task_id, payload.model_dump(), critical=False)


@router.post("/local-agent/tasks/{task_id}/critical-approval", response_model=LocalAgentTaskRecord)
def critical_approval_local_agent_task(task_id: str, payload: LocalAgentApprovalIn) -> dict:
    return local_agent_service.approve_task(task_id, payload.model_dump(), critical=True)


@router.get("/local-agent/dashboard", response_model=LocalAgentDashboard)
def local_agent_dashboard() -> dict:
    return local_agent_service.dashboard()


@router.post("/agent/v1/heartbeat", response_model=LocalAgentRecord)
def agent_heartbeat(x_forja_agent_id: str | None = Header(default=None), authorization: str | None = Header(default=None)) -> dict:
    agent = _agent_from_headers(x_forja_agent_id, authorization)
    return local_agent_service.heartbeat(agent)


@router.post("/agent/v1/tasks/poll")
def agent_poll_tasks(
    payload: LocalAgentTaskPollIn,
    x_forja_agent_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    agent = _agent_from_headers(x_forja_agent_id, authorization)
    return local_agent_service.poll_tasks(agent, payload.model_dump())


@router.post("/agent/v1/tasks/{task_id}/lease", response_model=LocalAgentLeaseRecord)
def agent_lease_task(task_id: str, x_forja_agent_id: str | None = Header(default=None), authorization: str | None = Header(default=None)) -> dict:
    agent = _agent_from_headers(x_forja_agent_id, authorization)
    return local_agent_service.lease_task(task_id, agent)


@router.post("/agent/v1/tasks/{task_id}/heartbeat", response_model=LocalAgentTaskRecord)
def agent_task_heartbeat(task_id: str, x_forja_agent_id: str | None = Header(default=None), authorization: str | None = Header(default=None)) -> dict:
    agent = _agent_from_headers(x_forja_agent_id, authorization)
    return local_agent_service.task_heartbeat(task_id, agent)


@router.post("/agent/v1/tasks/{task_id}/events", response_model=LocalAgentTaskRecord)
def agent_record_event(
    task_id: str,
    payload: LocalAgentEventIn,
    x_forja_agent_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    agent = _agent_from_headers(x_forja_agent_id, authorization)
    return local_agent_service.record_event(task_id, agent, payload.model_dump())


@router.post("/agent/v1/tasks/{task_id}/snapshot", response_model=LocalAgentTaskRecord)
def agent_record_snapshot(
    task_id: str,
    payload: LocalAgentSnapshotIn,
    x_forja_agent_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    agent = _agent_from_headers(x_forja_agent_id, authorization)
    return local_agent_service.record_snapshot(task_id, agent, payload.snapshot)


@router.post("/agent/v1/tasks/{task_id}/backup", response_model=LocalAgentTaskRecord)
def agent_record_backup(
    task_id: str,
    payload: LocalAgentBackupIn,
    x_forja_agent_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    agent = _agent_from_headers(x_forja_agent_id, authorization)
    return local_agent_service.record_backup(task_id, agent, payload.backup)


@router.post("/agent/v1/tasks/{task_id}/rollback-record", response_model=LocalAgentTaskRecord)
def agent_record_rollback(
    task_id: str,
    payload: LocalAgentRollbackIn,
    x_forja_agent_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    agent = _agent_from_headers(x_forja_agent_id, authorization)
    return local_agent_service.record_rollback(task_id, agent, payload.rollback)


@router.post("/agent/v1/tasks/{task_id}/logs", response_model=LocalAgentTaskRecord)
def agent_record_log(
    task_id: str,
    payload: LocalAgentCommandLogIn,
    x_forja_agent_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    agent = _agent_from_headers(x_forja_agent_id, authorization)
    return local_agent_service.record_log(task_id, agent, payload.command_log)


@router.post("/agent/v1/tasks/{task_id}/artifacts", response_model=LocalAgentTaskRecord)
def agent_record_artifact(
    task_id: str,
    payload: LocalAgentArtifactIn,
    x_forja_agent_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    agent = _agent_from_headers(x_forja_agent_id, authorization)
    return local_agent_service.record_artifact(task_id, agent, payload.artifact)


@router.post("/agent/v1/tasks/{task_id}/results", response_model=LocalAgentTaskRecord)
def agent_record_result(
    task_id: str,
    payload: LocalAgentResultIn,
    x_forja_agent_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    agent = _agent_from_headers(x_forja_agent_id, authorization)
    return local_agent_service.record_result(task_id, agent, payload.result)
