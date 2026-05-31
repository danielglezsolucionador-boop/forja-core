from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.operational_loop_service import (
    build_loop_manager,
    correction_loop_manager,
    delivery_package_manager,
    retry_policy_manager,
    validation_loop_manager,
)


router = APIRouter(prefix="/operational-loop", tags=["operational-loop"])


class BuildLoopStartIn(BaseModel):
    sender: str = Field(default="ceo", max_length=80)
    recipient: str = Field(default="forja", max_length=80)
    input: str = Field(min_length=1, max_length=4000)
    source_request_id: str | None = Field(default=None, max_length=120)
    manual_approval: bool = False


class ValidationLoopIn(BaseModel):
    request_id: str | None = Field(default=None, max_length=120)
    workspace_id: str | None = Field(default=None, max_length=120)
    sender: str = Field(default="system", max_length=80)
    build_record: dict | None = None


class CorrectionLoopIn(BaseModel):
    request_id: str | None = Field(default=None, max_length=120)
    sender: str = Field(default="system", max_length=80)
    validation_report: dict


class RetryPolicyIn(BaseModel):
    operation_id: str | None = Field(default=None, max_length=120)
    request_id: str | None = Field(default=None, max_length=120)
    failure_type: str = Field(default="unknown_failure", max_length=80)
    retry_count: int = 0
    retry_reason: str | None = Field(default=None, max_length=400)
    reason: str | None = Field(default=None, max_length=400)


class DeliveryPackageIn(BaseModel):
    request_id: str | None = Field(default=None, max_length=120)
    sender: str = Field(default="system", max_length=80)
    build_record: dict | None = None
    validation_report: dict | None = None
    correction_report: dict | None = None


@router.get("/status")
def operational_loop_status() -> dict:
    return {
        "status": "ready",
        "build_loop": build_loop_manager.status(),
        "validation_loop": validation_loop_manager.latest(),
        "correction_loop": correction_loop_manager.latest(),
        "retry_policy": retry_policy_manager.latest(),
        "delivery_package": delivery_package_manager.latest(),
        "external_commands_enabled": False,
    }


@router.get("/latest")
def latest_operational_loop() -> dict:
    return {
        "build_loop": build_loop_manager.latest(),
        "validation_loop": validation_loop_manager.latest(),
        "correction_loop": correction_loop_manager.latest(),
        "retry_policy": retry_policy_manager.latest(),
        "delivery_package": delivery_package_manager.latest(),
    }


@router.post("/build/start")
def start_build_loop(payload: BuildLoopStartIn) -> dict:
    return build_loop_manager.start(payload.model_dump())


@router.post("/validation/run")
def run_validation_loop(payload: ValidationLoopIn) -> dict:
    return validation_loop_manager.validate(payload.model_dump())


@router.post("/correction/run")
def run_correction_loop(payload: CorrectionLoopIn) -> dict:
    return correction_loop_manager.correct(payload.model_dump())


@router.post("/retry/evaluate")
def evaluate_retry_policy(payload: RetryPolicyIn) -> dict:
    return retry_policy_manager.evaluate(payload.model_dump())


@router.post("/delivery/create")
def create_delivery_package(payload: DeliveryPackageIn) -> dict:
    return delivery_package_manager.create(payload.model_dump())
