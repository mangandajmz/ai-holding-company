# Pending Decision: Missing Persona Scope Map Contract

Date: 2026-05-09

## Context

The overnight build prompt said to read `docs/personas/persona-scope-map.md`
first because it is the contract. That file did not exist at build start.

## Conservative Action Taken

Created a v0 scope map from the already-approved architecture:

- Personas are conversational entry points to structured skills underneath.
- Default opening responses are deterministic queries against `state/` and
  `reports/`.
- Model-assisted conversation is allowed only for follow-up after deterministic
  state has been retrieved and rendered.
- Telegram is demoted to pager/fallback rail; the operating room should become
  the primary employee-feeling surface.

## Owner Input Needed

Confirm whether this v0 scope map is the contract or whether any persona,
authority, or default opening should change before the operating room MVP moves
from scaffold to active workflow.

