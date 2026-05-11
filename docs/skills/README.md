# Skill Contracts

Skill contracts define repeatable operating workflows for the agent-manned SaaS
company. They are not a separate runtime framework.

Runtime should use existing rails first:

- `scripts/tool_router.py`
- `scripts/aiogram_bridge.py`
- `reports/`
- `state/`
- `memory/`
- `docs/decisions/`

## Contract Fields

Each skill should define:

- Name.
- Owner agent.
- Vertical.
- Autonomy: Auto, Approve, or Guardrail.
- Inputs.
- Outputs.
- Report/state paths.
- Natural owner-facing behavior.
- Structured record fields.
- Success metrics.
- Never rules.

## Naming

Markdown filenames can use hyphens, for example:

```text
docs/skills/risk-aggregate-daily.md
```

Runtime commands should use underscores because Telegram commands are safer that
way:

```text
risk_aggregate_daily
```

## First Skills To Formalize

- `risk-aggregate-daily`
- `backtest-review`
- `data-quality-daily`
- `content-brief-to-draft`
- `analytics-weekly`
- `portfolio-retro-weekly`
- `support-triage`
- `pre-deploy-checklist`
- `broker-reconcile`
