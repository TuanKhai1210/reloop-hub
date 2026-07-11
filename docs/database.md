# Database Setup

This document describes the local PostgreSQL setup and database workflow for the ReLoop Hub backend.

## Technology

- Python 3.13
- PostgreSQL 18
- FastAPI
- SQLAlchemy 2
- Alembic
- Psycopg 3
- Pydantic Settings

## Create the virtual environment

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Configure environment variables

Copy the environment template:

```powershell
Copy-Item .env.example .env
```

Update `.env`:

```env
DATABASE_URL=postgresql+psycopg://reloop_app:YOUR_PASSWORD@localhost:5432/reloop_hub
APP_ENV=development
APP_NAME=ReLoop Hub API
DEBUG=true
```

Do not commit `.env`.

## Configure the isolated test database

Database integration tests must never use the development database.

Create the local test environment file:

```powershell
Copy-Item .env.test.example .env.test
```

Update the password in `.env.test` and keep these values:

```env
APP_ENV=test
DEBUG=false
TEST_DATABASE_URL=postgresql+psycopg://reloop_app:YOUR_PASSWORD@localhost:5432/reloop_hub_test
```

Create the PostgreSQL test database with `reloop_app` as its owner:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\createdb.exe" `
    -h 127.0.0.1 `
    -p 5432 `
    -U postgres `
    -W `
    -O reloop_app `
    reloop_hub_test
```

Apply Alembic migrations to `reloop_hub_test` before running tests.

The test suite exits without running tests when:

- `APP_ENV` is not `test`
- `TEST_DATABASE_URL` is missing
- the configured database name does not end with `_test`
- the connected database does not match `TEST_DATABASE_URL`

Do not commit `.env.test`.

## Create the PostgreSQL user and database

Run through pgAdmin or PostgreSQL:

```sql
CREATE USER reloop_app WITH PASSWORD 'YOUR_PASSWORD';
CREATE DATABASE reloop_hub OWNER reloop_app;
```

## Test the database connection

```powershell
python -m scripts.check_database
```

Expected output:

```text
Database connection successful.
```

## Apply database migrations

```powershell
python -m alembic upgrade head
```

Check the current revision:

```powershell
python -m alembic current
```

Current initial revision:

```text
7ef98cb4e30a (head)
```

Check for differences between the models and the database:

```powershell
python -m alembic check
```

Expected output:

```text
No new upgrade operations detected.
```

## Seed demo data

```powershell
python -m scripts.seed_database
```

First run:

```text
Database seed completed.
Created: 6
Skipped: 0
```

Later runs:

```text
Database seed completed.
Created: 0
Skipped: 6
```

The seed script creates:

- One demo student
- One demo administrator
- One demo driver
- One campus canteen Hub
- Two canteen vouchers

## Initial database tables

- `users`
- `hubs`
- `return_sessions`
- `material_batches`
- `bottle_transactions`
- `point_ledger`
- `vouchers`
- `voucher_redemptions`
- `pickups`
- `verification_events`

Alembic also creates the `alembic_version` table.

## Database ownership

The database owner maintains:

- `app/core/config.py`
- `app/core/database.py`
- `app/models/`
- `app/repositories/`
- `alembic/`
- Database migration files
- Database seed scripts
- `.env.example`

The API owner maintains:

- `app/main.py`
- `app/api/`
- `app/schemas/`
- `app/services/`
- API tests

## Migration workflow

Only the database owner creates Alembic revisions.
After changing models:

```powershell
python -m alembic revision --autogenerate -m "describe schema change"
```

Review the generated migration, then run:

```powershell
python -m alembic upgrade head
python -m alembic check
```

The API owner runs:

```powershell
git pull
python -m alembic upgrade head
```

## Git workflow

Database branch:

```text
feature/database-foundation -> dev
```

API branch:

```text
feature/api-base -> dev
```

Deployment flow:

```text
dev -> main -> deployment
```

## Commit messages

Use Conventional Commits:

```text
<type>(<scope>): <short description>
```

Examples:

```text
feat(db): add database model
fix(db): correct foreign key constraint
chore(db): update seed data
docs(db): add database setup guide
```
