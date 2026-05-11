# portfolio-retro-weekly

## Owner Agent

Chief of Staff.

## Vertical

Holdco.

## Autonomy

Auto.

## Purpose

Run a weekly portfolio retro that pulls outputs from agents, commits/deploys
where locally available, incidents, approvals, decisions, and unresolved issues.

## Current Runtime Mapping

- Skill runtime: `scripts/skill_portfolio_retro_weekly.py`
- Legacy scheduled runtime: `scripts/weekly_retro.py`
- Existing state: `state/retro_state.json`
- Existing reports: `reports/retros/`
- Skill reports: `reports/skills/portfolio-retro-weekly/`

Run locally through the Telegram/tool router:

```powershell
python scripts/tool_router.py portfolio_retro_weekly
```

Telegram command:

```text
/portfolio_retro_weekly
```

## Inputs

- `reports/skills/`
- `reports/phase3_holding_latest.*`
- Board approval state.
- Content decisions.
- Company loops.
- Local commit/deploy notes where available.
- Incident notes.

## Outputs

- Weekly retro.
- Decisions logged.
- Open issues and owners.
- Follow-through for the next week.

## Success Metrics

- Weekly consistency.
- Decisions logged per retro.
- Repeated unresolved issues become visible.

## Never

- Never turn the retro into a raw log dump.
- Never lose owner decisions in chat only.
