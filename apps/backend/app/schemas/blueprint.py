from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.intent import IntentDomain, IntentInterpretation, IntentRequestType, IntentResponseTarget, IntentRiskLevel, IntentSender


class ProjectBlueprintIn(BaseModel):
    interpretation: IntentInterpretation
    source_request_id: str | None = Field(default=None, max_length=120)


class BlueprintEndpoint(BaseModel):
    method: str
    path: str
    purpose: str


class BlueprintDataEntity(BaseModel):
    name: str
    fields: list[str]
    purpose: str


class BlueprintRisk(BaseModel):
    level: IntentRiskLevel
    title: str
    mitigation: str


class ProjectBlueprint(BaseModel):
    blueprint_id: str
    source_request_id: str
    sender: IntentSender
    response_target: IntentResponseTarget
    project_name: str
    project_type: IntentRequestType
    domain: IntentDomain
    objective: str
    stack_recommendation: list[str]
    suggested_structure: list[str]
    modules: list[str]
    screens: list[str]
    endpoints: list[BlueprintEndpoint]
    data_model: list[BlueprintDataEntity]
    risks: list[BlueprintRisk]
    risk_level: IntentRiskLevel
    approval_required: bool
    construction_steps: list[str]
    validation_criteria: list[str]
    created_at: str
