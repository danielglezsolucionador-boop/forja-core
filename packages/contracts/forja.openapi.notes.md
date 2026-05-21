# FORJA API Contract Notes

The authoritative OpenAPI contract is exposed by the local backend at `/openapi.json`.

Core operational contracts:

- `GET /health`
- `POST /auth/login`
- `GET /auth/me`
- `GET /runtime/status`
- `POST /telemetry/events`
- `POST /notifications`
- `POST /governance/approval-requests`
- `POST /factory/requests`
- `GET /ecosystem/integrations`
- `POST /workflows`
- `GET /validation/operational`

All mutating factory and workflow endpoints are designed around auditability and human checkpoints.
