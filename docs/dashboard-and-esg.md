# Dashboard and ESG data contract

## Period semantics

Both reporting endpoints accept `day`, `week`, or `month`:

```text
GET /api/v1/dashboard/summary?period=day
GET /api/v1/reports/esg?period=month
```

Periods are calendar periods in `REPORTING_TIMEZONE` rather than rolling
24-hour, 7-day, or 30-day windows:

- `day`: local midnight to request time;
- `week`: Monday local midnight to request time;
- `month`: first day of the local month to request time.

Every response includes `period_start`, `period_end`, and
`reporting_timezone` so the frontend can label charts without guessing.

## KPI definitions

| KPI | Definition |
|---|---|
| Participants | Distinct users with at least one bottle transaction in the period |
| Successful transactions | Accepted bottle transactions in the period |
| Success rate | Accepted / all bottle transactions |
| Recovered plastic | Sum of accepted bottle weight |
| Average AI confidence | Mean stored confidence for inspected bottles |
| Average cleanliness | Mean stored cleanliness score for inspected bottles |
| Distance saved | Completed-route baseline distance minus optimized distance, never below zero |
| Collection efficiency | Recovered kilograms / optimized route kilometre |
| Vehicle utilization | Actual collected load / total capacity of completed-route vehicles |
| CO2 saved | Distance saved multiplied by the configured emission factor |
| Traceability completeness | Accepted transactions with at least one trace event / accepted transactions |

Hub online counts and ready batches are current operational snapshots. They
are intentionally not historical period aggregates.

## Feedstock quality

Bottle inspection stores `ai_confidence`, `cleanliness_score`, material,
weight, outcome and rejection reason. Hub telemetry stores camera status,
sensor status, fill level, weight and optional temperature. Historical Hub
telemetry is available at:

```text
GET /api/v1/hubs/{hub_code}/telemetry?period=week
```

The backend consumes results produced by a Hub, camera, sensor or external
AI module. It does not perform computer-vision inference itself.

## ESG caution

`CO2_EMISSION_FACTOR_KG_PER_KM` defaults to `0.27` only for prototype
demonstration. Set `CO2_FACTOR_SOURCE` and `CO2_METHODOLOGY_VERSION` to an
approved, documented methodology before using the number in an external
ESG report. The API returns all three fields for auditability.
