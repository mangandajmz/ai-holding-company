# risk-aggregate-daily

## Owner Agent

Chief of Staff, with Risk Officer input.

## Vertical

Holdco.

## Autonomy

Auto for brief generation. Approve for actions created from the brief.

## Purpose

Produce a one-page daily cross-portfolio risk brief covering trading, websites,
cost/cash-relevant signals when available, anomalies, and owner decisions.

## Current Runtime Mapping

- Existing source: `scripts/phase3_holding.py`
- Existing CLI: `python scripts/tool_router.py run_holding --mode heartbeat --force`
- Future alias: `python scripts/tool_router.py risk_aggregate_daily --force`
- Latest reports: `reports/phase3_holding_latest.*`

## Inputs

- `reports/daily_brief_latest.*`
- `reports/phase2_divisions_latest.*`
- `reports/phase3_holding_latest.*`
- `state/board_approval_decisions.json`
- `state/property_metric_feed.json`
- `memory/`

## Outputs

- Natural CEO-facing brief.
- Structured sidecar for status, sources, owner needs, and handoffs.
- Approval items when action requires owner approval.

## Success Metrics

- Less than five minutes to understand the company.
- At least one useful issue per month surfaced before becoming a problem.
- No invented status, revenue, trades, approvals, or decisions.

## Never

- Never approve actions for the owner.
- Never hide missing or stale inputs.
- Never route around the approval system.
