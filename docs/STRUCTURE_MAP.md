# Current Structure Map

The target `company_os/` concept maps cleanly onto the current repo. Keep these
equivalents unless the current layout starts slowing down daily CEO review.

| Target concept | Current location | Notes |
|---|---|---|
| CEO inbox | Telegram via `scripts/aiogram_bridge.py` | Commands and approvals flow through the bridge. |
| Approvals | `state/board_approval_decisions.json` | Board approvals, content decisions, and developer approvals are local state. |
| Daily reports | `reports/daily_brief_*.md` | Latest pointer is `reports/daily_brief_latest.md`. |
| Division reports | `reports/phase2_divisions_*.md` | Latest pointer is `reports/phase2_divisions_latest.md`. |
| CEO summaries | `reports/phase3_holding_*.md` | Board pack mode is the strongest CEO review artifact. |
| KPI scorecards | `reports/*_latest.json`, `config/targets.yaml` | JSON report payloads hold the structured scorecards. |
| Memory | `memory/` | Local vector memory only. |
| Archives | `reports/` timestamped files, `artifacts/` | Avoid moving generated history until report volume causes friction. |
| Divisions | `crews/*.yaml`, `scripts/phase2_crews.py` | Runtime division definitions and orchestration. |
| Agent prompts/configs | `crews/`, `config/` | No separate prompt tree needed yet. |
| Workflows/docs | root runbooks, `docs/` | New operator-facing docs live in `docs/`. |
| Websites | `finance_web_page/`, `free-utility-tools/`, `free-traderhub-research-team/` | Website source remains protected by approval rules. |
| Agent staff contracts | `docs/agents/` | First-wave role contracts for the agent-manned company. |
| Skill contracts | `docs/skills/` | Repeatable operating workflows; runtime still uses existing rails. |
| Communication rules | `docs/communication/` | Natural conversation on the surface, structured truth underneath. |

## Keep

- `scripts/aiogram_bridge.py` as the sole automation and owner interaction path.
- `scripts/tool_router.py` as the local command entry point.
- `scripts/phase2_crews.py` and `scripts/phase3_holding.py` as the reporting and CEO layers.
- `crews/*.yaml` for the current compact role model.
- `reports/`, `state/`, `memory/`, `config/`, and `tests/`.

## Clarify

- Old OpenClaw references are deprecated and should not guide new work.
- `reports/` is flat but functional. Archive only when it becomes hard to scan.
- Website QA should be captured as simple checklists before adding more browser automation.
- Agent contracts describe responsibilities before runtime. They do not require
  separate runtime agents until a recurring business function is proven.
- Natural agent communication is owner-facing. Structured records still belong
  in `reports/`, `state/`, `memory/`, and `docs/decisions/`.

## Add Later Only If Needed

- A physical `company_os/` folder.
- A separate runtime agent framework.
- Report archiving scripts.
- More agent roles or external chat surfaces.
