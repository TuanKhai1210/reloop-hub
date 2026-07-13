# Unified backend

The former `fastapi-backend` prototype used a separate SQLite database and
duplicated the `users` and `hubs` tables. Its supported capabilities have
been integrated into the root PostgreSQL backend. The standalone SQLite
runtime must not be restored or deployed.

## Canonical mappings

| Prototype API concept | Canonical domain |
|---|---|
| Deposit | ReturnSession + BottleTransaction |
| PointsLedger | PointLedger |
| Hub load | Hub telemetry + material batches |
| Collection route | CollectionRoute + RouteStop |
| Pickup event | Pickup + MaterialBatch |
| Trace record | TraceEvent + VerificationEvent |

## Dashboard contract

`GET /api/v1/dashboard/summary?period=day|week|month` returns a calendar
period in `REPORTING_TIMEZONE`. It includes participation, accepted and
rejected bottles, PET/HDPE volume, AI confidence, cleanliness, rejection
reasons, Hub/camera/sensor status, pickup readiness, route distance,
vehicle utilization, collection efficiency, estimated CO2 savings and
traceability completeness.

`GET /api/v1/reports/esg?period=...` exposes the same auditable period
window together with the configured CO2 factor, source note and
methodology version. The default factor is a prototype assumption and must
be replaced by an approved local factor before the output is used as a
formal ESG claim.

The current route optimizer is a capacity-constrained nearest-neighbor
heuristic using Hub coordinates and collection readiness. It is an MVP
optimizer, not a complete road-network DVRP solver.

Accepted material is traceable through `DEPOSITED`, `HUB_STORED`,
`PICKED_UP` and `RECEIVED`. An ADMIN, OPERATOR or RECYCLER records the final
receipt through `POST /api/v1/traceability/batches/{batch_id}/receive`.

Routers perform HTTP validation and authorization only. Cross-table writes
are owned by application services and committed by the request database
dependency.

## Production requirements

- configure a strong JWT secret and device API key;
- run Alembic migrations before starting the application;
- use HTTPS and restrict CORS origins;
- store secrets in the deployment secret manager;
- run PostgreSQL backups and monitor connection-pool saturation;
- never enable automatic schema creation.
