# ReLoop Hub Frontend

React/Vite prototype for ReLoop Hub's verified PET/HDPE reverse-logistics system.

## Modes

- Demo mode (`VITE_DEMO_MODE=true`) uses clearly labelled campus sample data and does not claim live impact.
- Connected mode (`VITE_DEMO_MODE=false`) authenticates against the FastAPI backend and loads protected dashboard data with JWT bearer tokens.

Copy `.env.example` to `.env`, then configure the API and WebSocket URLs for your environment.

## Commands

```bash
npm ci
npm run dev
npm run lint
npm test
npm run build
```

## Backend contract

The frontend uses these endpoints:

- `POST /api/v1/auth/token`
- `GET /api/v1/auth/me`
- `GET /api/v1/dashboard/summary?period=day|week|month`
- `GET /api/v1/reports/esg?period=day|week|month`
- `GET /api/v1/hubs`
- `GET /api/v1/hubs/{code}/telemetry?period=...`
- `GET /api/v1/routes`
- `GET /api/v1/deposits`
- `GET /api/v1/users`
- `GET /api/v1/vouchers`
- `GET /api/v1/traceability/{trace_code}`
- `WS /ws/hubs?token=...`

Staff dashboard access is enforced by the backend's JWT and role checks. No PIN or credential is stored in the frontend bundle.
