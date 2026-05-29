FORJA
=====

Operational source path:
`C:\Users\admin\Desktop\forja`

Current state:
- vNext operator experience completed locally.
- Source traceability initialized in Phase E2.
- Official remote/cloud deployment remains blocked until a GitHub repository and cloud credentials are configured.

Cloud foundation target:
- Frontend: Vercel, root directory `frontend`, build command `npm run build`, output directory `build`.
- Backend: Render, root directory `backend`, build command `pip install -r requirements.txt`, start command `uvicorn main:app --host 0.0.0.0 --port $PORT`.

Required production secrets:
- `JWT_SECRET_KEY`
- `FORJA_ADMIN_USERNAME`
- `FORJA_ADMIN_PASSWORD_HASH`
- `ALLOWED_ORIGINS`
- `REACT_APP_FORJA_API_URL` for frontend builds

Security note:
FORJA does not ship a default admin password. If auth is not configured, protected login returns an unavailable/auth-not-configured state instead of accepting hardcoded credentials.
