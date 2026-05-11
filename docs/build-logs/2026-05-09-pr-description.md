# PR Description: Persona Operating Room MVP

## First Thing To Look At

1. Start with `docs/personas/persona-scope-map.md`.
2. Confirm the rule: persona openings are deterministic, no model calls.
3. Open `operating-room/index.html` after generating `operating-room/snapshot.json`.
4. Review `docs/decisions/_pending/missing-persona-scope-map.md`.
5. Check whether the Finance/Admin deferral is acceptable.

## What Was Built

- Created `docs/personas/persona-scope-map.md` as the v0 persona contract.
- Added persona shells under `docs/personas/<persona>/contract.md` for:
  - Chief of Staff
  - Risk Officer
  - Quant Ops
  - Growth Lead
  - Editorial Lead
  - Engineering/Ops
  - Support Lead
  - Finance/Admin deferred stub
- Added deterministic read-only operating room scaffolding:
  - `scripts/operating_room_snapshot.py`
  - `operating-room/index.html`
  - `operating-room/app.js`
  - `operating-room/styles.css`
  - `operating-room/README.md`
  - `operating-room/snapshot.json`
- Added `memory/schema.md`.
- Added templates:
  - `docs/decisions/_template.md`
  - `retros/_template.md`
- Added DRAFT Shadow skill specs for persona-named missing skills:
  - `ask-company`
  - `seo-review`
  - `infra-cost-review`
  - `monthly-close-prep`
  - `compliance-monitor`
  - `skill-perf-review`
- Added tests for the operating-room snapshot builder.

## What Was Skipped And Why

- No Slack or Telegram expansion: the current architecture demotes Telegram to
  pager/fallback and does not choose Slack yet.
- No live persona chat: default openings must be deterministic first.
- No Finance/Admin activation: reliable finance/cost/cash sources are not wired.
- No protected property changes: MT5, TraderHub, utility sites, research team,
  and `projects/` were left untouched.
- No external calls: the web app reads local `snapshot.json`; no webhooks,
  email, Telegram, model, or HTTP API calls were added.

## Pending Decisions

- `docs/decisions/_pending/missing-persona-scope-map.md`

## Validation

- `python -m pytest tests\test_operating_room_snapshot.py -q` passed.
- `python -m pytest tests\test_operating_room_snapshot.py tests\test_aiogram_bridge.py tests\test_tool_router_ask_company.py -q` passed.
- `python -m py_compile scripts\operating_room_snapshot.py scripts\aiogram_bridge.py scripts\tool_router.py` passed.
- `python -m pytest tests -q` passed: 229 tests.

