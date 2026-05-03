# Roadmap: MVP to Vision

## Current Forward Focus

The next phase is not a rebuild. The local operating shell already exists. The
priority now is to make FreeTraderHub the first measurable operating property:
truthful promotion gates, live or manually refreshed KPI feed, closed-loop
initiative artifacts, QA discipline, and CEO approval records for risky actions.

Do not create a parallel `company_os/` tree while the current `reports/`,
`state/`, `memory/`, `crews/`, `config/`, `scripts/`, and `docs/` structure is
working.

## v0.1 - Clean Local Folder-Based Operating System

Status: mostly complete through existing `reports/`, `state/`, `memory/`,
`crews/`, `config/`, and `scripts/`.

- Reports: complete.
- Templates: added under `docs/templates/`.
- CEO inbox: Telegram bridge.
- Pending approvals: existing board/content/developer approval flows.
- Basic scripts: existing report and bridge scripts cover the MVP.

## v0.2 - Local AI Summaries

Status: partially complete.

- Ollama-first rule exists.
- Local memory exists.
- Keep human approval mandatory.

## v0.3 - Telegram Heartbeat

Status: complete.

- `scripts/aiogram_bridge.py --send-morning-brief`
- Observer mode remains default.
- Risky action execution remains gated.

## v0.4 - Routing Through Chat

Status: use Telegram bridge, not OpenClaw.

- Route tasks, reports, approvals, and notes through Telegram.
- Keep OpenClaw prohibited unless the rule is explicitly changed later.

## v0.5 - Website QA Automation

Status: next practical expansion after FreeTraderHub metrics are trustworthy.

- Start with the QA checklists in `docs/website_qa/`.
- Add browser automation only for checks that repeat often and catch real issues.

## v0.5a - FreeTraderHub Operating Property Hardening

Status: current priority.

- Update FTH property gates so they reflect the real strategy and KPI model.
- Feed FTH metrics into `state/property_metric_feed.json` or its successor:
  traffic, tool completion, email list size, affiliate progress, alert/Pro MRR,
  content production, costs, and risks.
- Run each meaningful FTH initiative through the closed-loop workflow:
  goal, evidence, review, CEO approval where needed, action, measurement, result.
- Keep Content Studio brief-driven and CEO-gated.
- Use website QA checklists before calling public-facing work done.

## v0.6 - Trading Research Workflow

Status: planned, with guardrails already present.

- Market watch reports.
- Risk manager checks.
- Alert review.
- No live execution without CEO approval.

## v0.7 - Approved-Action Automation

Status: future.

- Automate only after explicit CEO approval.
- Log every action, result, and measurement.
