from __future__ import annotations

from fastapi import APIRouter

from app.schemas.intent import IntentInterpretation, IntentInterpretationIn
from app.services.intent_service import intent_interpreter_service


router = APIRouter(prefix="/intent", tags=["intent-interpreter"])


@router.post("/interpret", response_model=IntentInterpretation)
def interpret_intent(payload: IntentInterpretationIn) -> dict:
    return intent_interpreter_service.interpret(payload.model_dump())
