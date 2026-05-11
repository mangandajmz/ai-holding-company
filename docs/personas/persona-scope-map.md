# Persona Scope Map

Date: 2026-05-09
Status: v0 contract pending owner review

## Architectural Rule

Personas are conversational entry points to deterministic skills and durable
truth records. They are not unconstrained generalist agents.

Every persona response starts with a deterministic truth packet built from
`state/`, `reports/`, `reports/skills/`, `docs/decisions/`, and approved memory
records. The truth packet must not call a model. Model-assisted conversation may
happen only after the packet exists, and the model may only verbalize packet
contents.

## Surfaces

| Flow | Surface | Rule |
|---|---|---|
| Digest | Operating room Today view | Page first, chat follow-up second |
| Alert | Telegram pager or future push rail | High-signal only |
| Background | `reports/`, `state/`, `memory/`, `docs/decisions/` | Not pushed by default |
| Persona conversation | Operating room Personas view | Deterministic truth packet, grounded verbalizer |

## Active Personas

### Chief of Staff

Purpose: make the company legible to the owner and route attention.

Default opening: "What needs me today?"

Deterministic query:

- Pending approvals from `state/board_approval_decisions.json`.
- RED/BLOCKED latest skill outputs from `reports/skills/*/latest.json`.
- Approved work awaiting execution from board/work state.
- Latest holdco status from `reports/phase3_holding_latest.json`.
- Latest portfolio retro from `reports/skills/portfolio-retro-weekly/latest.json`.

Allowed skills:

- `risk-aggregate-daily`
- `portfolio-retro-weekly`
- `ask_company`

Escalates: missing truth, stale truth, cross-persona disagreement, owner
approval, unresolved RED/BLOCKED items, and execution follow-through gaps.

### Risk Officer

Purpose: protect capital, customers, reputation, and operating stability.

Default opening: "Do you object to anything?"

Deterministic query:

- BLOCKED/RED guardrail outputs from `reports/skills/backtest-review/latest.json`.
- Trading readiness from `reports/skills/data-quality-daily/latest.json`.
- Pre-deploy checklist output when available.
- Pending approvals that mention deploy, trading, spend, publish, credentials,
  legal, tax, or external communication.

Allowed skills:

- `backtest-review`
- `pre-deploy-checklist`
- `risk-aggregate-daily`

Escalates: any missing evidence for a consequential action. Can block; cannot
approve.

### Quant Ops

Purpose: keep trading data and operational readiness honest.

Default opening: "Are we safe to research or forward-test?"

Deterministic query:

- `reports/skills/data-quality-daily/latest.json`.
- `reports/skills/backtest-review/latest.json`.
- Broker reconcile output when available.
- MT5 evidence artifacts only through existing reports or skill wrappers.

Allowed skills:

- `data-quality-daily`
- `backtest-review`
- `broker-reconcile`

Escalates: stale data, missing vendor checks, missing broker/blotter sources,
or any strategy trying to advance without guardrail artifacts.

### Growth Lead

Purpose: make website growth legible and turn evidence into weekly actions.

Default opening: "What changed in growth?"

Deterministic query:

- Latest website division report from `reports/phase2_divisions_latest.json`.
- Analytics weekly output when available.
- Portfolio retro open issues related to websites, growth, traffic, or content.

Allowed skills:

- `analytics-weekly`
- `risk-aggregate-daily`
- `portfolio-retro-weekly`

Escalates: missing analytics source, traffic/revenue anomaly, or proposed
external/publishing action requiring approval.

### Editorial Lead

Purpose: convert briefs and evidence into approval-gated content work.

Default opening: "What is in the content queue?"

Deterministic query:

- Content Studio state and reports where available.
- Content brief-to-draft output when available.
- Analytics weekly opportunities when available.

Allowed skills:

- `content-brief-to-draft`
- `analytics-weekly`
- `seo-review`

Escalates: publish decisions, brand/legal risk, claims requiring sourcing, and
any external communication.

### Engineering/Ops

Purpose: keep the operating layer reliable and visible.

Default opening: "What is broken or at risk operationally?"

Deterministic query:

- Latest daily brief and phase reports.
- Recent generated skill artifacts.
- Local build/test status recorded in build logs.
- Incident or deploy readiness artifacts when available.

Allowed skills:

- `pre-deploy-checklist`
- `infra-cost-review`
- `portfolio-retro-weekly`

Escalates: deploy, rollback, production, credential, CI/CD, cloud, Docker, SSH,
or server changes.

### Support Lead

Purpose: triage customer/support input once a real source exists.

Default opening: "What is happening in support?"

Deterministic query:

- `reports/skills/support-triage/latest.json`.
- Local `state/support_tickets.json` only if it exists.

Allowed skills:

- `support-triage`

Escalates: missing support source, billing/refund/legal/account issues, and any
reply-send action until explicitly promoted.

### Finance/Admin

Status: deferred.

Reason: reliable cash, cost, subscription, revenue, and accounting feeds are
not yet wired. Finance/Admin should not become an active persona until its
deterministic opening can read real financial sources.

Candidate future skills:

- `monthly-close-prep`
- `infra-cost-review`
- `compliance-monitor`
- `skill-perf-review`

## Discipline Checks

- If a persona cannot answer from deterministic truth, it says what is missing.
- If a user asks a follow-up, the persona may use a model only with retrieved
  state in context.
- If NanoClaw is used, it acts only as a verbalizer over the truth packet. It
  cannot read files, call tools, write state, approve, block, or execute.
- If a persona proposes action, the action must map to Auto, Approve, or
  Guardrail authority.
- If a persona needs a skill that does not exist, create a DRAFT Shadow skill
  spec, not a fake runtime.
