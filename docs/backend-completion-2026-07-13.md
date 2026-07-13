# Backend completion review - 2026-07-13

## Requirement alignment

| Web requirement | Backend support |
|---|---|
| Realtime Smart Hub status | Telemetry API, current Hub state, telemetry history, WebSocket events |
| Collection optimization | Capacity-aware nearest-neighbor route generation using ready batches, Hub fill state and coordinates |
| Feedstock quality | AI confidence, cleanliness score, material, weight, liquid/foreign-object flags, accept/reject reason and verification events |
| Users, transactions and rewards | JWT/RBAC, return sessions, bottle transactions, Green Points ledger, voucher issue and voucher use |
| Environmental/logistics indicators | Recovered kg, participants, successful transactions, baseline/optimized distance, saved distance, kg/km, vehicle utilization and estimated CO2 |
| End-to-end traceability | Deposit, Hub storage, pickup and recycler receipt stages |
| ESG reporting | Calendar day/week/month windows with explicit start, end, timezone and CO2 methodology metadata |

## New and changed API contracts

```text
GET  /api/v1/dashboard/summary?period=day|week|month
GET  /api/v1/reports/esg?period=day|week|month
GET  /api/v1/hubs/{hub_code}/telemetry?period=day|week|month
POST /api/v1/deposits/sessions/{session_id}/complete
POST /api/v1/deposits/sessions/{session_id}/cancel
POST /api/v1/vouchers/redemptions/{redemption_code}/use
POST /api/v1/traceability/batches/{batch_id}/receive
```

Dashboard and ESG endpoints are limited to `ADMIN`, `OPERATOR`, and
`RECYCLER`. A `DRIVER` may execute only a route assigned to that driver.

## Database change

Alembic revision `d81f4a6b2c09` adds a nullable, constrained
`bottle_transactions.cleanliness_score` column. Existing rows remain valid;
new device inspections persist the score for quality analytics.

The migration was verified with upgrade, downgrade, upgrade, and
`alembic check` on PostgreSQL 18.

## Test isolation

`python -m scripts.prepare_test_database` reads `.env.test`, refuses a
database whose name does not end in `_test`, and upgrades it to Alembic
head. Pytest now checks all model tables and the exact Alembic head before
running. This prevents a stale test schema from producing cascading
`UndefinedColumn` and `NoSuchTable` failures.

Validation result for this delivery:

```text
160 passed
No new upgrade operations detected.
```

## Honest MVP boundaries

- The backend consumes camera/AI/sensor results; it does not run a computer
  vision model.
- Route generation is a geographic nearest-neighbor heuristic with vehicle
  capacity. It is not yet a road-network VRP/DVRP solver.
- WebSocket broadcasting is in-process; multiple API replicas require a
  broker such as Redis Pub/Sub.
- Device authentication still uses one environment-level key. Production
  deployment needs per-Hub keys, rotation and revocation.
- Smart Hub offline queuing and replay belong to firmware/device gateway
  integration and are not implemented here.
- The default CO2 factor is a visible prototype assumption. Replace it with
  an approved factor and source before external ESG reporting.
- Recycler receipt records a facility code but the prototype does not yet
  implement organization tenancy or bind each recycler user to one facility.
