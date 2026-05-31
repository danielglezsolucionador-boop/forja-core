# FORJA Operational Core Final

Date: 2026-05-26

## What FORJA Can Do Now

- Interpret CEO and mock Cerebro requests.
- Generate ProjectBlueprint records from interpreted intent.
- Create isolated workspaces under `.forja/workspaces/<request_id>/`.
- Generate controlled initial files for app, API, dashboard, and module requests.
- Build workflow requests as governed workspace/delivery packages without complex code generation.
- Validate workspace structure, base documents, outputs, audit artifacts, timeline artifacts, and workspace manifests.
- Apply safe automatic corrections for missing README, execution report, outputs, audit placeholders, timelines, docs/tests folders, and workspace manifests.
- Classify failures and allow only safe retry scenarios.
- Create delivery packages with summary, next steps, manifest, validation report, correction report, architecture, execution report, blueprint, and audit summary.
- Expose operational loop status in the Human Console.
- Prepare agent contracts for CEO, Cerebro, Hermes, and FORJA.
- Validate ecosystem messages with correlation IDs, response targets, payloads, approvals, capability requirements, and audit metadata.
- Prepare Hermes memory bridge and Cerebro control bridge in mock/prep mode only.
- Record orchestration trails by correlation ID.
- Keep AI Gateway economic routing as the default operational provider strategy.

## What FORJA Cannot Do Yet

- Connect to real Hermes runtime.
- Connect to real Cerebro runtime.
- Execute unlimited or mass AI generation.
- Deploy generated projects automatically.
- Repair existing external projects automatically.
- Bypass governance, approval, safe mode, retry policy, or workspace isolation.
- Complete real economic AI calls until the economic provider credentials are configured.

## Builder Core

Builder Core remains workspace-isolated and governed. It interprets, blueprints, creates safe workspaces, generates controlled starter files, records outputs, and blocks high-risk modifications.

## AI Gateway

Economic provider routing is primary. DeepSeek is the default economic provider and Qwen is the economic fallback profile. OpenAI and Anthropic remain prepared as premium future providers.

## Operational Loop

The operational loop includes:

- BuildLoopManager
- ValidationLoopManager
- CorrectionLoopManager
- RetryPolicyManager
- DeliveryPackageManager

All managers operate without external shell commands and write project artifacts only inside `.forja/workspaces`.

## Hermes Prep

HermesMemoryBridge is prepared in mock mode. It can create operational memory payloads, execution summaries, workspace manifest payloads, audit summaries, and status snapshots. It does not call real Hermes.

## Cerebro Prep

CerebroControlBridge is prepared in mock mode. It can receive mock orders, create approval requests, send mock results, send capability requests, send audit summaries, and report control status. It does not call real Cerebro.

## Limits

- Medium-risk builds require approval.
- High-risk repair/upgrade remains blocked.
- Retry policy blocks unsafe operations, governance bypass, duplicates, secret exposure, dangerous overwrite, DB/security failures, and Render config failures.
- Delivery packages are review artifacts, not deployable production releases.

## Rollback

Rollback target:

- Branch: `forja-operational-core-final`
- Tag: `forja-operational-core-v1`
- Backup archive: `C:\Users\admin\forja-backups\forja-operational-core-source-no-secrets-YYYYMMDD-HHMMSS.zip`

## URLs

- Frontend: https://forja-frontend.onrender.com/#human-console-preview
- Backend: https://forja-core.onrender.com

## Validations

Required validation set:

- `python -m compileall apps/backend/app tools -q`
- `pytest -q`
- `npm run build`
- `python tools/validate_forja.py`
- `git diff --check`
- backend `/health`
- backend `/runtime/status`
- frontend smoke
- mobile smoke
- console errors `[]`

## Next Steps

- CTO/CEO review.
- Configure economic provider credentials if real economic AI execution is required.
- Keep Hermes and Cerebro bridges in mock mode until the next approved integration phase.
