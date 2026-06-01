# CENTINELA - GOVERNANCE EVIDENCE LAYER

Generated: 2026-05-26

## Policy Registry Fields

- policy_id,
- name,
- version,
- severity,
- trigger,
- action,
- approval_required,
- freeze_condition,
- owner,
- created_at.

## Decision Audit Trail Fields

- decision_id,
- actor,
- timestamp,
- event,
- evidence,
- risk_resolved,
- operational_impact,
- ecosystem_impact,
- approval_context,
- protected_state,
- response_target.

## Freeze Conditions

- unstable,
- corrupted,
- governance compromised,
- resilience degraded,
- dangerous refactor risk,
- ecosystem threat.

## CEO Override

CEO override is allowed and must be recorded with:

- actor,
- reason,
- risk accepted,
- expected impact,
- protected state,
- rollback plan.

## Anti-Loop Protection

If repeated remediation attempts do not improve measurable state, Centinela must stop, preserve logs, and request CEO validation.

