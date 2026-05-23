# FORJA Creator Cloud Validation

Validation date: 2026-05-23

Stable target: FORJA Creator Console, controlled Execution Engine, and Output Manager on Render cloud.

## URLs

- Frontend: https://forja-frontend.onrender.com
- Backend: https://forja-core.onrender.com
- Health: https://forja-core.onrender.com/health
- Runtime: https://forja-core.onrender.com/runtime/status

## Render Surfaces Validated

- Backend web service: `forja-core`
- Frontend static site: `forja-frontend`
- PostgreSQL: connected through backend runtime telemetry
- Render config: not changed during this phase

## Endpoints Validated

- `GET /health`
- `GET /runtime/status`
- `GET /creator/console`
- `POST /creator/commands`
- `POST /creator/commands/{command_id}/decision`
- `POST /creator/commands/{command_id}/execute`
- `GET /creator/commands/{command_id}/outputs`
- `GET /creator/outputs`
- `GET /creator/outputs/{output_id}`
- `GET /creator/outputs/{output_id}/metadata`
- `OPTIONS /creator/console`

## Cloud Results

- Backend health: `ok`
- Runtime status: `active`
- Database status: `ok`
- CORS preflight from `https://forja-frontend.onrender.com`: `200`
- CORS allow origin: `https://forja-frontend.onrender.com`
- Frontend cloud page title: `FORJA Enterprise Core Runtime`
- Frontend console errors: none observed during browser smoke

## Flow Tested

### User request

1. Created command with `sender=user`.
2. Initial status: `awaiting_approval`.
3. Tried execution before approval.
4. Result: `blocked`, response `missing_human_approval`.
5. Approved through human approval endpoint.
6. Approval status: `approved`.
7. Executed with `metadata_only=true`.
8. Final status: `completed`.
9. Response: `metadata_only_completed_for_user`.
10. Timeline visible and contains execution events.
11. Output type validated: `workflow_plan`.
12. Output mode validated: `metadata_only_output`.
13. Metadata download returned `200` with attachment disposition.

### Cerebro request

1. Created command with `sender=cerebro`.
2. Initial status: `awaiting_approval`.
3. Approved through human approval endpoint.
4. Executed with `metadata_only=true`.
5. Final status: `completed`.
6. Response: `metadata_only_completed_for_cerebro`.

### Governance blocked request

1. Created command requesting external provider execution.
2. Result: `blocked`.
3. Response: `blocked_provider_disabled`.
4. Output Manager shows `blocked_action_report`.
5. Result Viewer lists produced governance trace, not-produced source code/deployable app/files, and governance blocks.

## Creator Console

- Creator Console loads in the cloud frontend.
- Command input is visible.
- Sender controls include `user`, `cerebro`, `seo`, and `system`.
- Request pipeline is visible.
- Approval center is visible.
- Execution timeline is visible.
- Audit stream is visible.
- Output Manager is visible.

## Execution Engine

Validated pipeline:

- `received`
- `governance_check`
- `awaiting_approval`
- `approved`
- `executing`
- `completed`
- `blocked`
- `failed`

Critical gate validated:

- Execution before human approval does not run.
- Metadata-only execution runs only after approval.
- External provider execution remains disabled.
- No autonomous writes were enabled.

## Output Manager

Validated output behavior:

- Outputs are associated to the originating request.
- Outputs expose sender separation.
- Result Viewer shows produced items.
- Result Viewer shows not-produced items.
- Result Viewer shows governance blocks.
- Metadata downloads are available through backend endpoint.
- Output records explicitly state `metadata_only_output`.

Validated output types during cloud smoke:

- `workflow_plan`
- `api_blueprint`
- `execution_summary`
- `blocked_action_report`

## Audit

Audit stream validated through Creator Console response.

Observed event classes:

- `creator.command_created`
- `creator.approval_decision`
- `creator.execution_attempted`

## DB

Runtime telemetry reports:

- `database.status=ok`

This validates that the backend sees the cloud database as reachable. Creator command/output state is currently handled through FORJA state storage; persistent Creator history across Render restarts should be treated as a separate hardening item if long-term retention is required.

## Mobile

Mobile smoke viewport:

- `390x844`

Validated:

- Creator Console renders.
- Header and command panel fit the viewport.
- Sender controls wrap.
- Status badge wraps.
- Quick command controls stack.
- No frontend console errors observed during browser smoke.

Screenshots:

- `.forja/state/forja-phase4-desktop-validation.png`
- `.forja/state/forja-phase4-mobile-validation.png`
- `.forja/state/forja-phase4-output-manager-validation.png`

## Local Validation

Commands executed:

```powershell
pytest -q
npm run build
python tools\validate_forja.py
```

Results:

- `pytest -q`: `15 passed`, with one existing non-blocking runtime warning in `test_runtime_is_honest_about_no_busy_loop`.
- `npm run build`: OK.
- `python tools\validate_forja.py`: OK.

## Risks

- Creator/output history is metadata-only and currently tied to FORJA state storage behavior. Render restarts can clear non-persistent runtime state unless backed by durable storage for this subsystem.
- Execution remains intentionally metadata-only. It does not create deployable files, call providers, write source code, run migrations, or deploy infrastructure.
- External AI provider execution remains blocked by governance.
- The frontend is a public operational view; sensitive operations should stay behind authenticated/governed backend routes before any future write-enabled phase.

## Rollback

Stable tag:

```powershell
git fetch --tags origin
git checkout forja-creator-cloud-v1
```

Fast rollback procedure:

1. In Render, redeploy backend from tag/commit `forja-creator-cloud-v1`.
2. In Render, redeploy frontend from tag/commit `forja-creator-cloud-v1`.
3. Validate:

```powershell
Invoke-RestMethod https://forja-core.onrender.com/health
Invoke-RestMethod https://forja-core.onrender.com/runtime/status
```

4. Open:

```text
https://forja-frontend.onrender.com
```

5. Confirm Creator Console, Execution Engine, Output Manager, audit stream, and dashboard are visible.

## Final State

FORJA Creator/Execution/Output is cloud-valid as a controlled metadata-only operating layer:

- Cloud frontend online.
- Cloud backend online.
- Cloud DB reachable.
- Creator Console functional.
- Execution Engine guarded by human approval.
- Output Manager functional.
- Audit visible.
- CORS valid for frontend origin.
- Mobile smoke valid.
- Rollback path documented.
