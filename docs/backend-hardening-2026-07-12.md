# Backend hardening — 2026-07-12

This change set closes the main consistency and concurrency gaps identified
after the Return and Voucher services were merged.

## Functional changes

- request database dependency commits on success and rolls back on failure;
- bottle transaction codes and verifier names are normalized;
- Green Points are calculated by a server-owned reward policy;
- accepted bottles transition material batches and Hub fill status;
- production `PickupService` creates pickups, assigns batches, completes
  collection, releases Hub inventory, and cancels planned pickups;
- repository listing is deterministic and capped at 1,000 records per page.

## Database changes

Migration `85c4b02d47a1` adds:

- non-negative User balance and return counters;
- ReturnSession status/time consistency;
- BottleTransaction accepted/rejected outcome consistency;
- MaterialBatch pickup consistency;
- Pickup status/time consistency;
- VoucherRedemption usage consistency;
- restrictive audit foreign keys for verification, pickup batches, and
  drivers.

The migration supports both upgrade and downgrade.

## Operational changes

- failed test-database connections no longer expose credentials in pytest
  tracebacks;
- database pool sizing and connection timeout are configurable;
- GitHub Actions starts PostgreSQL 18, applies migrations, runs tests, and
  checks schema drift.

## Validation

Validation was performed against an isolated PostgreSQL 18.4 instance:

```text
134 passed
Alembic downgrade -1: passed
Alembic upgrade head: passed
No new upgrade operations detected.
```

Before merging, run the same commands against the team test database:

```powershell
python -m alembic upgrade head
python -m pytest -q -p no:cacheprovider
python -m alembic check
```
