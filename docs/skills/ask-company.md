---
status: DRAFT
owner: Chief of Staff
autonomy_level: Shadow
version: 0.1.0
last_reviewed: 2026-05-09
---

# ask-company

## Purpose

Answer owner questions from deterministic company truth before any follow-up
conversation.

## Inputs

- `reports/phase3_holding_latest.json`
- `reports/phase2_divisions_latest.json`
- `reports/daily_brief_latest.json`
- `state/board_approval_decisions.json`
- `reports/skills/*/latest.json`
- `memory/` for context only

## Outputs

- Natural owner-facing answer.
- Owner need classification.
- Source list when requested or consequential.

## Shadow Rule

Default openings must not call a model. Follow-up conversation may use a model
only after deterministic state has been retrieved and rendered.

