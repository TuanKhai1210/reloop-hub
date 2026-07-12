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
