# ReLoop Hub showcase dataset

The showcase generator creates a deterministic, end-to-end dataset for
demonstrating the ReLoop Hub backend and dashboard. It is intended for local
development, presentations, API evaluation and frontend integration. It must
not be treated as evidence from a physical campus pilot.

## What the dataset covers

The default dataset spans 35 calendar days and contains:

- four HCMUT campus Hubs with current telemetry;
- 36 student accounts, one operator and one recycler account;
- accepted and rejected PET/HDPE bottle transactions;
- verification events and explicit rejection reasons;
- Green Points ledger entries and canteen voucher redemptions;
- PET/HDPE material batches in storing, ready and picked-up states;
- vehicles, pickups, completed collection routes and route stops;
- bottle-level trace events from deposit to Hub storage, pickup and recycler
  receipt;
- open operational records for the current dashboard state;
- sufficient current-day, current-week and current-month activity for all
  reporting filters.

The generator uses deterministic identifiers and a fixed random seed. Running
it again with the same arguments produces the same logical dataset relative to
the current date.

## Create the dataset from a clean local setup

From the repository root, activate the virtual environment and run:

```powershell
python -m alembic upgrade head
python -m scripts.seed_database
python -m scripts.seed_demo_dataset --reset
```

`--reset` deletes only records owned by this showcase generator before
rebuilding them. Baseline seed accounts and unrelated developer data are not
deleted. The command refuses to run when `APP_ENV=production`.

To create a different-sized dataset:

```powershell
python -m scripts.seed_demo_dataset `
  --reset `
  --days 60 `
  --students 80 `
  --sessions-per-day 24
```

Run `python -m scripts.seed_demo_dataset --help` for all options.

## Start and inspect the complete prototype

Start the backend from the repository root:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in a second terminal:

```powershell
Set-Location frontend
npm.cmd run dev -- --host 127.0.0.1
```

For live backend data, the frontend environment must contain:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
VITE_WS_BASE_URL=ws://127.0.0.1:8000
VITE_DEMO_MODE=false
```

Open `http://127.0.0.1:5173/` and sign in with a staff account.

## Demo accounts

| Role | Email | Password | Intended use |
|---|---|---|---|
| Admin | `admin@reloop.vn` | `Admin@123` | Full dashboard/API access |
| Operator | `demo.operator@reloop.vn` | `DemoStaff@123` | Recommended dashboard demo |
| Recycler | `demo.recycler@reloop.vn` | `DemoStaff@123` | Recycler receipt/trace demo |
| Student | `demo.student.01@reloop.vn` | `DemoStudent@123` | API-level student flow |

The current web dashboard is staff-facing. Student and driver workflows are
available through backend roles/APIs but are not separate frontend login
experiences yet.

## Validate day, week and month reports

After signing in, the dashboard period selector should return different values
for `day`, `week` and `month`. The corresponding endpoints are:

```text
GET /api/v1/dashboard/summary?period=day
GET /api/v1/dashboard/summary?period=week
GET /api/v1/dashboard/summary?period=month
GET /api/v1/reports/esg?period=month
```

The generator prints a validation summary for all three periods. It checks that
each period contains transactions and that every accepted bottle is traceable.
Environmental and CO2 values remain simulated prototype indicators until a
field baseline and real vehicle data are collected.

## Trace one bottle from end to end

At the end of generation, the command prints three sample transaction codes:

- a fully received bottle;
- a bottle currently stored at a Hub;
- a rejected bottle.

Use any printed code in:

```text
GET /api/v1/traceability/{transaction_code}
```

A fully completed trace contains this ordered lifecycle:

```text
DEPOSITED -> HUB_STORED -> PICKED_UP -> RECEIVED
```

A rejected bottle ends with `REJECTED`, while a current bottle may legitimately
stop at `HUB_STORED` until its batch is collected.

## Verification checklist

```powershell
python -m alembic check
python -m scripts.prepare_test_database
python -m pytest -q
```

Expected results are no pending Alembic operations and a passing backend test
suite. Tests use the isolated database configured by `.env.test`; never point
`TEST_DATABASE_URL` to the development database.

