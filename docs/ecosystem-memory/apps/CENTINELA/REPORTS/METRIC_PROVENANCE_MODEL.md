# CENTINELA - METRIC PROVENANCE MODEL

Generated: 2026-05-26

## Purpose

Prevent false premium risk by requiring every visible metric to declare its evidence state.

## Provenance States

- REAL: backed by live runtime event source.
- SIMULATED: generated for demo, test, or design state.
- STALE: previously real but older than accepted freshness window.
- UNKNOWN: visible but source is not available.

## Required Fields

Each metric must carry:

- metric_id,
- label,
- value,
- provenance_state,
- source,
- last_updated,
- confidence,
- affected_system,
- decision_impact.

## Metrics Covered

- security health score,
- threats blocked,
- prompts analyzed,
- active agents,
- system score,
- threat table,
- risk engine percentages,
- tool call counts,
- 24h summary.

## Human Cabin Rule

No visible metric may be presented as production truth unless provenance_state is REAL and source is known.

