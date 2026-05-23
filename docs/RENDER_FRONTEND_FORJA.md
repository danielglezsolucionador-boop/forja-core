# FORJA Frontend Render Static Site

Backend cloud:

```txt
https://forja-core.onrender.com
```

Create a Render Static Site:

```txt
Root Directory: apps/frontend
Build Command: npm install && npm run build
Publish Directory: dist
```

Environment variable:

```txt
VITE_FORJA_API_URL=https://forja-core.onrender.com
```

After the static site is created, update backend CORS if needed:

```txt
FORJA_FRONTEND_ORIGIN=https://<forja-frontend-static-site>.onrender.com
FORJA_CORS_ORIGINS=https://<forja-frontend-static-site>.onrender.com
```

The frontend consumes only:

```txt
GET /health
GET /runtime/status
```
