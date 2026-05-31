from __future__ import annotations

from app.core.audit import append_audit_event, utc_now
from app.services.intent_parser import parse_intent


class IntentInterpreterService:
    def interpret(self, payload: dict) -> dict:
        sender = payload.get("sender", "ceo")
        recipient = payload.get("recipient", "forja")
        raw_input = payload.get("input", "")
        append_audit_event(
            "intent_received",
            sender,
            {"recipient": recipient, "raw_input": raw_input},
            risk="low",
        )
        parsed = parse_intent(raw_input)
        response_target = self._response_target(sender)
        interpretation = {
            "sender": sender,
            "recipient": recipient,
            "request_type": parsed.request_type,
            "domain": parsed.domain,
            "objective": parsed.objective,
            "suggested_modules": parsed.suggested_modules,
            "risk_level": parsed.risk_level,
            "requires_approval": parsed.requires_approval,
            "response_target": response_target,
            "raw_input": raw_input,
            "normalized_input": parsed.normalized_input,
            "confidence": parsed.confidence,
            "timestamp": utc_now(),
        }
        audit_risk = parsed.risk_level.lower()
        append_audit_event(
            "interpreted_request",
            sender,
            {
                "recipient": recipient,
                "response_target": response_target,
                "request_type": parsed.request_type,
                "domain": parsed.domain,
                "confidence": parsed.confidence,
            },
            risk=audit_risk,
        )
        append_audit_event(
            "risk_detected",
            sender,
            {
                "request_type": parsed.request_type,
                "risk_level": parsed.risk_level,
                "requires_approval": parsed.requires_approval,
                "response_target": response_target,
            },
            risk=audit_risk,
        )
        return interpretation

    def _response_target(self, sender: str) -> str:
        if sender == "cerebro":
            return "cerebro"
        if sender == "seo":
            return "seo"
        if sender == "system":
            return "system"
        return "ceo"


intent_interpreter_service = IntentInterpreterService()
