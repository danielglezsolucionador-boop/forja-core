from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


IntentSender = Literal["ceo", "cerebro", "user", "seo", "system"]
IntentRecipient = Literal["forja"]
IntentResponseTarget = Literal["ceo", "cerebro", "seo", "system"]
IntentRequestType = Literal[
    "app",
    "api",
    "dashboard",
    "module",
    "workflow",
    "integration",
    "repair",
    "upgrade",
    "analysis",
    "document",
]
IntentDomain = Literal[
    "inventario",
    "ventas",
    "clientes",
    "financiero",
    "contable",
    "tributario",
    "WhatsApp",
    "ecommerce",
    "logistica",
    "RRHH",
    "general",
]
IntentRiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class IntentInterpretationIn(BaseModel):
    sender: IntentSender = "ceo"
    recipient: IntentRecipient = "forja"
    input: str = Field(min_length=1, max_length=4000)


class IntentInterpretation(BaseModel):
    sender: IntentSender
    recipient: IntentRecipient
    request_type: IntentRequestType
    domain: IntentDomain
    objective: str
    suggested_modules: list[str]
    risk_level: IntentRiskLevel
    requires_approval: bool
    response_target: IntentResponseTarget
    raw_input: str
    normalized_input: str
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: str
