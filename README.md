# ReLoop Hub Backend

Backend API for the ReLoop Hub project.

## Technology stack

- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Pydantic
- Psycopg

## Architecture

The repository contains one backend and one canonical PostgreSQL schema:

```text
FastAPI routers
    -> application services
    -> repositories
    -> SQLAlchemy Session
    -> PostgreSQL
```

Alembic is the only schema-management mechanism. The application never
calls `Base.metadata.create_all()` at startup and does not use SQLite.

## Features

- JWT authentication and role-based authorization
- Smart Hub device-key authentication and realtime telemetry
- verified PET/HDPE bottle acceptance and rejection
- Green Points ledger and voucher redemption
- material batch and pickup lifecycle
- collection vehicle routing and route stops
- bottle-level traceability
- dashboard and ESG reporting
- WebSocket Hub updates
- PostgreSQL concurrency and rollback tests

## Local setup

```powershell
python -m pip install -r requirements-dev.txt
python -m alembic upgrade head
python -m scripts.seed_database
python -m pytest -q -p no:cacheprovider
python -m uvicorn app.main:app --reload
```

Open the API documentation at:

```text
http://127.0.0.1:8000/docs
```

## Main API groups

```text
/api/v1/auth
/api/v1/hubs
/api/v1/deposits
/api/v1/vouchers
/api/v1/users
/api/v1/routes
/api/v1/traceability
/api/v1/dashboard
/api/v1/reports
/ws/hubs
```

Copy `.env.example` to `.env` and replace every `CHANGE_ME` value before
running outside local development. Never commit `.env` or `.env.test`.
