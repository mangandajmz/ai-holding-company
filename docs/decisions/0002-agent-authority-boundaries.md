# Decision 0002: Agent Authority Boundaries

Date: 2026-05-09

## Decision

Every agent action uses one authority category:

- Auto: agent executes and reports after the fact.
- Approve: agent proposes; owner approves once; agent executes.
- Guardrail: agent can block, but cannot approve.

## Default Boundaries

- Trading action: Guardrail or Approve, never fully Auto.
- Strategy promotion: Guardrail.
- Publishing and external communication: Approve.
- Spend, contracts, credentials, and business commitments: Approve or
  Guardrail.
- Legal/tax-sensitive work: Approve or Guardrail.
- Monitoring, internal summaries, and local report generation: Auto.
- Support routine replies: Approve until quality is proven.

## Rationale

The future company should feel manned, but it must not silently cross dangerous
business boundaries. Agents should move routine internal work while preserving
owner control over consequential actions.

## Consequences

- Risk Officer can block but cannot approve.
- Chief of Staff can route and recommend but cannot approve for the owner.
- Editorial can draft but cannot publish.
- Engineering/Ops can prepare and test but cannot deploy production without
  approval.
- Quant Ops can block readiness but cannot authorize live trading.

## Review Trigger

Revisit when an agent workflow repeatedly requires owner approval for low-risk
actions and there is enough quality evidence to consider a narrower Auto lane.
