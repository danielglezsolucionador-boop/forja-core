# FORJA Knowledge Core and Local Runtime

FORJA is the local technology factory for the ecosystem. This repository contains the phase documentation plus a local operational implementation for backend, frontend, reusable modules, governance, workflow orchestration, and auditability.

## Operating Rules

- Local-first: no cloud, no push, no remote repository.
- Zero write policy: factory execution cannot write generated output without a human approval record.
- Human-in-the-loop: risky actions remain blocked until explicitly approved.
- No fake readiness: endpoints report disabled, blocked, or pending states honestly.
- Hermes isolation: this repository does not modify Hermes runtime, backend, dashboard, Render, Railway, or production.

## Local Commands

Backend:

```powershell
cd C:\Users\admin\forja-knowledge-core\apps\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8100
```

Frontend:

```powershell
cd C:\Users\admin\forja-knowledge-core\apps\frontend
npm install
npm run dev
```

Validation:

```powershell
cd C:\Users\admin\forja-knowledge-core
python -m pytest apps/backend/tests -q
python tools/validate_forja.py
```
