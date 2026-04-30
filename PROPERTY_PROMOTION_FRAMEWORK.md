# Property Promotion Framework

## Goal
Promote a property from `revamp_queue` to operating portfolio only when it has:
- A defined business case
- A targeted product with clear user
- Feasibility and ROI validated
- Metrics defined and actively trackable

This framework is based on the FreeTraderHub revamp process and is now encoded in:
- `config/projects.yaml` -> `promotion_framework`
- `config/projects.yaml` -> `property_charters.<property>.promotion`
- `scripts/phase3_holding.py` -> revamp queue readiness evaluation

## Required Gates
Each revamp property must pass all gates:
1. `business_case_defined`
2. `target_product_defined`
3. `feasibility_validated`
4. `roi_case_defined`
5. `metrics_defined`
6. `metrics_trackable`

Plus a minimum live-tracking requirement:
1. `live_metrics_count >= min_live_metrics`

## Metrics Expectations
For each property, define:
- `metrics_defined`: metrics that prove value (for example demand, activation, completion, revenue)
- `tracked_metrics`: metrics currently being collected in telemetry
- `live_metrics_count`: count of metrics actively tracked right now

## Promotion Rule
Status becomes `READY_FOR_PROMOTION` when:
1. All required gates pass
2. Live metrics minimum is met

Until then, status is `REVAMP_IN_PROGRESS` and property remains excluded from company score.

## Operating Workflow
1. Keep property at `charter.version: v0-stub` while revamping.
2. Use `run_holding --mode heartbeat --force` to view revamp queue readiness.
3. When `READY_FOR_PROMOTION` is achieved, promote by updating charter from `v0-stub` to active version (for example `v1`).
4. After promotion, property moves into operating score automatically and is no longer shown as parked.

