# analytics-weekly

## Owner Agent

Growth Lead.

## Vertical

Websites.

## Autonomy

Auto for internal digest. Approve for external or spend actions.

## Purpose

Create a weekly website analytics digest that surfaces anomalies, explains what
changed, and recommends evidence-backed growth decisions.

## First Scope

FreeTraderHub first. Do not generalize to every property until another property
has reliable metrics.

## Inputs

- `state/property_metrics/freetraderhub/shared.json`
- `state/property_metric_feed.json`
- `reports/phase3_holding_latest.*`
- FreeTraderHub research reports.
- Content output and draft state.

## Outputs

- Weekly digest in `reports/skills/analytics-weekly/`.
- Anomaly list.
- Recommended growth decisions.
- Editorial or Engineering/Ops handoffs.

## Success Metrics

- Anomalies surfaced versus baseline.
- Decisions per digest.
- Owner no longer has to manually inspect every dashboard.

## Never

- Never guess missing dashboard values.
- Never call external analytics APIs without explicit approval and credentials
  already configured safely.
- Never recommend spend without approval.
