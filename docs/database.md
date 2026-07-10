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
DATABASE\_URL=postgresql+psycopg://reloop\_app:YOUR\_PASSWORD@localhost:5432/reloop\_hub
APP\_ENV=development
APP\_NAME=ReLoop Hub API
DEBUG=true
```

Do not commit `.env`.

## Create the PostgreSQL user and database

Run through pgAdmin or PostgreSQL:

```sql
CREATE USER reloop\_app WITH PASSWORD 'YOUR\_PASSWORD';
CREATE DATABASE reloop\_hub OWNER reloop\_app;
```

## Test the database connection

```powershell
python -m scripts.check\_database
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
python -m scripts.seed\_database
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
- `return\_sessions`
- `material\_batches`
- `bottle\_transactions`
- `point\_ledger`
- `vouchers`
- `voucher\_redemptions`
- `pickups`
- `verification\_events`

Alembic also creates the `alembic\_version` table.

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
