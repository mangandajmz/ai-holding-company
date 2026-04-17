# Stage G — Commercial Division
## Claude Code Prompts

**Stage G context (read before starting):**
Stage D is complete. Trading=GREEN, Websites=GREEN, commit e533073, 23/23 tests passing.
G1 is unblocked. Commercial Division is the next item on the critical path (PLAN.md §11.2).

**Philosophy (per CLAUDE.md — non-negotiable):**
- No overengineering. Three similar lines > a premature utility.
- No new helpers without removing a duplicate. Edit utils.py only if you are deleting a duplicate.
- No config options for things that have one correct value.
- New files only when genuinely justified — prefer editing existing ones.
- shell=False always for subprocess calls. shlex.split() on config-sourced strings.
- No LLM arithmetic. Python tools only for all financial calculations.
- Model for Commercial: llama3.1:8b (same as MA and Phase 3 CEO layer).

**Existing patterns to follow (study before writing anything new):**
- Crew YAML: `crews/trading_bots_division.yaml` and `crews/websites_division.yaml`
- Phase orchestration: `scripts/phase2_crews.py`
- Shared helpers: `scripts/utils.py` — use existing helpers, add none without removing one
- Config: `config/projects.yaml` and `config/targets.yaml`
- Report output: `reports/phase2_divisions_latest.json` pattern

---

## CODEX REVIEW GATE — Standard Process (runs after EVERY block)

After completing a block's success criteria, submit all files created or modified in
that block to Codex for review before moving to the next block. This gate is mandatory.
It was established in Stage D (commit e533073) and applies to every stage going forward.

**Codex must check all three categories:**

**1. STYLE / LINTING**
- Python: PEP 8 compliance, consistent naming conventions, no unused imports
- YAML: 2-space indentation, no duplicate keys, valid structure
- JSON: valid syntax, consistent formatting

**2. LOGIC**
- Edge cases: what happens if any input is None, empty, 0, or malformed?
- Graceful degradation: does the code return a safe default or raise unhelpfully?
- Data flow: does the output structure match what the consuming function expects?
- Off-by-one risks in any loops, slices, or index operations

**3. SECURITY (per PLAN.md R1, R8, CLAUDE.md)**
- `shell=False` confirmed on every subprocess call — no exceptions
- `shlex.split()` used on every config-sourced command string
- No hardcoded secrets, tokens, API keys, or credentials
- No cloud API calls — no openai, anthropic, requests to external AI endpoints (R1)
- No file writes outside `ai-holding-company/` directory scope (R8)
- No new network connections introduced without explicit CEO approval

**After Codex review:**
- Resolve ALL flagged issues — no partial fixes
- Re-run the block's success criteria checks after any fix
- Only proceed to the next block once Codex returns clean on all three categories

---

## BLOCK 1 — Commercial Division Crew YAML

```
Read PLAN.md and CLAUDE.md completely before doing anything.

Create one new file: crews/commercial_division.yaml

Model this on crews/trading_bots_division.yaml and crews/websites_division.yaml —
same structure, same YAML schema. Study both files before writing anything.

The Commercial Division has four agents (per PLAN.md §9):

AGENT 1 — commercial_manager
  role: "Commercial Division Manager"
  goal: "Deliver a concise weekly commercial brief covering financial health, active
         initiative scores, and risk flags. Surface only decisions that need CEO attention."
  backstory: "You run the business-management function for AI Holding Company. You coordinate
              finance reporting, initiative scoring, ROI analysis, and risk monitoring. You
              follow the Board Pack format (PLAN.md §8) for every recommendation."
  allow_delegation: true

AGENT 2 — finance_reporter
  role: "Finance Reporter"
  goal: "Produce an accurate daily PNL roll-up and weekly P&L statement from MT5 and
         Polymarket data. No estimates — only figures that can be verified from log data."
  backstory: "You extract financial data from bot logs and produce clean, factual summaries.
              You never invent numbers. If data is missing, you report it as missing."
  allow_delegation: false

AGENT 3 — commercial_analyst
  goal: "Score new initiatives against the Board Pack criteria (PLAN.md §8): expected upside,
         effort/cost, confidence level, and go/no-go recommendation."
  role: "Commercial Analyst"
  backstory: "You assess feasibility and ROI for proposed initiatives. You are the guardrail
              before anything reaches the Board Pack. You are skeptical by default and require
              evidence for optimistic projections."
  allow_delegation: false

AGENT 4 — risk_monitor
  role: "Risk Monitor"
  goal: "Detect drawdown breaches, cost spikes, and exposure flags against thresholds in
         config/targets.yaml. Produce a clear risk status: GREEN, AMBER, or RED."
  backstory: "You monitor financial risk for the holding company. You compare actual figures
              against defined thresholds and flag any breach immediately."
  allow_delegation: false

TASKS (follow the exact same task structure as trading_bots_division.yaml):

TASK 1 — finance_task (agent: finance_reporter)
  Produces the PNL roll-up. Input: MT5 and Polymarket KPI data from the daily brief payload.
  Output fields: mt5_pnl, polymarket_pnl, total_pnl, data_freshness, missing_data_flags.

TASK 2 — risk_task (agent: risk_monitor)
  Compares PNL and drawdown against config/targets.yaml thresholds.
  Output fields: drawdown_status (GREEN/AMBER/RED), cost_spike_detected (bool),
  exposure_flags (list), risk_verdict.

TASK 3 — scoring_task (agent: commercial_analyst)
  Scores any pending initiative from the CEO queue. If queue is empty, scores the
  top-priority item from PLAN.md §11 (next stage on critical path).
  Output fields: initiative_name, upside, effort, confidence, go_no_go, rationale.

TASK 4 — commercial_brief_task (agent: commercial_manager)
  Synthesises tasks 1–3 into a concise commercial brief.
  Output: structured dict matching the pattern of trading_bots_division.yaml manager task.
  Status field must be one of: GREEN, AMBER, RED.

RULES:
- Match the YAML structure of existing crew files exactly. Same key names, same indentation.
- Do not add keys that don't exist in the other crew files unless strictly required.
- verbose: false (same as other crews).
- manager_agent: "commercial_manager"

SUCCESS CRITERIA:
- crews/commercial_division.yaml is valid YAML (run: python -c "import yaml; yaml.safe_load(open('crews/commercial_division.yaml'))")
- Structure matches crews/trading_bots_division.yaml schema
- No existing files modified
```

> **→ CODEX REVIEW GATE** — run on `crews/commercial_division.yaml` before Block 2.
> Check: YAML syntax, consistent structure vs existing crew files, no duplicate keys. Full gate in CLAUDE.md.

---

## BLOCK 2 — Commercial Python Module

```
Read PLAN.md and CLAUDE.md completely before doing anything.
Block 1 must be complete before starting this block.

Create one new file: scripts/commercial.py

This module implements the four Commercial sub-functions (PLAN.md §9) and integrates
with the existing phase2_crews.py orchestration pattern.

Study these files carefully before writing a single line:
  - scripts/phase2_crews.py  — understand _ensure_brief_payload, _load_shared_targets,
                                the run_phase2_divisions pattern, and how division results
                                are structured
  - scripts/utils.py         — use existing helpers (load_yaml, fmt_money, parse_float,
                                now_utc_iso, reports_dir). Add nothing to utils.py.
  - config/targets.yaml      — understand the threshold structure

MODULE STRUCTURE (four functions, one per sub-function):

1. finance_report(brief_payload: dict, config: dict) -> dict
   Extracts MT5 PNL, Polymarket PNL from the brief_payload (same payload used by
   phase2_crews.py). Returns a dict with:
     mt5_pnl: float | None
     polymarket_pnl: float | None
     total_pnl: float | None
     data_freshness: str   (ISO timestamp of the source data)
     missing_data_flags: list[str]
   CRITICAL: All arithmetic in Python. No LLM calculations.

2. risk_check(brief_payload: dict, targets: dict) -> dict
   Compares PNL and drawdown from brief_payload against thresholds in targets.
   Returns a dict with:
     drawdown_status: str   ("GREEN" | "AMBER" | "RED")
     cost_spike_detected: bool
     exposure_flags: list[str]
     risk_verdict: str      ("GREEN" | "AMBER" | "RED")
   Threshold keys to use from targets.yaml:
     company.max_drawdown_pct.target_max  → RED above this
     company.max_drawdown_pct.amber_max   → AMBER above this
   CRITICAL: All comparisons in Python. No LLM judgement for threshold checks.

3. score_initiative(initiative_text: str, config: dict) -> dict
   Uses llama3.1:8b (via Ollama, same pattern as phase2_crews.py) to score a proposed
   initiative against the Board Pack criteria (PLAN.md §8).
   Returns a dict with all eight Board Pack fields populated.
   If initiative_text is empty or None, return a dict with status="no_initiative_pending".
   CRITICAL: The LLM provides qualitative scoring only. No LLM arithmetic anywhere.

4. run_commercial_division(config: dict, force: bool = False) -> dict
   The main entry point. Mirrors the run_phase2_divisions(config, force) signature pattern.
   Steps:
     a. Load brief payload via _ensure_brief_payload pattern (copy the import from phase2_crews.py)
     b. Load targets via _load_shared_targets
     c. Call finance_report()
     d. Call risk_check()
     e. Return a combined result dict with:
          division: "commercial"
          status: str   (worst of finance + risk verdicts → GREEN/AMBER/RED)
          finance: dict (from finance_report)
          risk: dict    (from risk_check)
          generated_at: str (ISO timestamp)
   Do NOT call score_initiative() from run_commercial_division — scoring is on-demand
   via Telegram command only, not part of the automated daily run.

IMPORTS AND DEPENDENCIES:
- Use only imports already present in phase2_crews.py or the Python stdlib.
- Import from utils: load_yaml, fmt_money, parse_float, now_utc_iso, reports_dir
- Import from monitoring: ROOT
- Do not add new dependencies to requirements.txt without explicit CEO approval.

RULES:
- No overengineering. If a helper already exists in utils.py, use it.
- shell=False for any subprocess. shlex.split() on config-sourced strings.
- No new files beyond scripts/commercial.py.
- No LLM arithmetic. Python only for all financial calculations.

SUCCESS CRITERIA:
- python -c "from commercial import run_commercial_division; print('ok')" exits 0
- finance_report() returns correct structure with None values when data is missing
  (do not raise exceptions on missing data — degrade gracefully)
- risk_check() correctly classifies GREEN/AMBER/RED against targets.yaml thresholds
- run_commercial_division() returns a dict with division, status, finance, risk, generated_at
```

> **→ CODEX REVIEW GATE** — run on `scripts/commercial.py` before Block 3.
> Check: PEP 8, no LLM arithmetic anywhere, all None/missing data paths handled gracefully,
> shell=False on any subprocess, no cloud API imports. Full gate in CLAUDE.md.

---

## BLOCK 3 — Config Wiring

```
Read PLAN.md and CLAUDE.md completely before doing anything.
Blocks 1 and 2 must be complete before starting this block.

Edit two existing config files. No new files.

---

EDIT 1 — config/projects.yaml

Add a commercial_division section. Study the existing structure carefully and match
its indentation and style exactly. Add this block at the end of the file, before any
trailing comments:

commercial_division:
  enabled: true
  model: "ollama/llama3.1:8b"
  ollama_base_url: "http://127.0.0.1:11434"
  spec_file: "crews/commercial_division.yaml"
  reports:
    json_latest: "reports/commercial_latest.json"
  initiative_queue_file: "state/initiative_queue.json"

---

EDIT 2 — config/targets.yaml

Add a commercial section. Add this block after the existing websites section:

commercial:
  max_drawdown_pct:
    target_max: 3.0
    amber_max: 5.0
  weekly_pnl_floor_usd:
    target_min: 0.0
    amber_min: -30.0
  initiative_score_threshold:
    go_min: 0.65
  max_unscored_initiatives: 0

---

EDIT 3 — state/initiative_queue.json  (create if missing)

The initiative queue stores pending CEO-submitted initiatives awaiting Commercial scoring.
Create state/initiative_queue.json with this initial content:

{
  "queue": [],
  "last_updated": ""
}

RULES:
- Edit only the three files above. No other changes.
- Do not alter any existing YAML keys — append only.
- Valid YAML/JSON after edits — run syntax checks.

SUCCESS CRITERIA:
- config/projects.yaml parses without error and contains commercial_division section
- config/targets.yaml parses without error and contains commercial section
- state/initiative_queue.json exists and contains {"queue": [], "last_updated": ""}
```

> **→ CODEX REVIEW GATE** — run on `config/projects.yaml`, `config/targets.yaml`, `state/initiative_queue.json` before Block 4.
> Check: valid YAML/JSON, no existing keys altered, no secrets introduced. Full gate in CLAUDE.md.

---

## BLOCK 4 — Phase 2 Integration

```
Read PLAN.md and CLAUDE.md completely before doing anything.
Blocks 1–3 must be complete before starting this block.

Edit one existing file: scripts/phase2_crews.py

The goal is to add the Commercial division to the Phase 2 orchestration alongside the
existing Trading and Websites divisions. Study phase2_crews.py thoroughly before writing
anything — understand how run_phase2_divisions() loads and runs each division crew.

CHANGE 1 — Import the new module at the top of phase2_crews.py:
  Add after the existing local imports:
    from commercial import run_commercial_division as _run_commercial

CHANGE 2 — In run_phase2_divisions() (or equivalent orchestration function):
  Add a call to _run_commercial(config=config, force=force) in the same place and
  pattern as the Trading and Websites division calls.
  Store the result as commercial_result and include it in the returned divisions dict
  under the key "commercial".

CHANGE 3 — In the status aggregation logic (where trading/websites statuses are combined
  into the overall company status):
  Include commercial_result["status"] in the worst-status calculation so that a
  Commercial RED can surface to the CEO layer.

CHANGE 4 — In the report output (the JSON written to reports/phase2_divisions_latest.json):
  Add the commercial result under a "commercial" key, matching the structure used for
  "trading" and "websites".

DO NOT:
- Refactor the existing trading or websites division logic.
- Change any existing function signatures.
- Add abstraction layers or base classes.
- Modify utils.py.

RULES:
- Make the minimum change that integrates commercial into the existing flow.
- If the integration requires more than ~30 lines of new code in phase2_crews.py,
  stop and check — you are probably overengineering it.

SUCCESS CRITERIA:
- python -c "from phase2_crews import run_phase2_divisions; print('ok')" exits 0
- run_phase2_divisions() result dict contains a "commercial" key
- reports/phase2_divisions_latest.json contains "commercial" section after a run
- All existing tests still pass: python -m pytest (or the project's test command)
```

> **→ CODEX REVIEW GATE** — run on modified `scripts/phase2_crews.py` before Block 5.
> Check: no existing function signatures changed, integration adds ≤30 lines,
> no abstraction layers introduced, all existing tests still pass. Full gate in CLAUDE.md.

---

## BLOCK 5 — Telegram Commands

```
Read PLAN.md and CLAUDE.md completely before doing anything.
Blocks 1–4 must be complete before starting this block.

Edit one existing file: scripts/telegram_bridge.py (or tool_router.py — check which
file handles Telegram command routing for the existing /scheduler and /violations commands,
then edit that file).

Add two new commands:

COMMAND 1 — /commercial
  Triggers run_commercial_division() and returns the result as a formatted Telegram message.
  Format (match the style of existing brief messages):
    📊 COMMERCIAL — [GREEN/AMBER/RED]
    PNL: MT5 £X.XX | Polymarket £X.XX | Total £X.XX
    Risk: [status] [any flags]
    Generated: [timestamp]
  If data is missing, show "n/a" not an error.
  Import: from commercial import run_commercial_division

COMMAND 2 — /score <initiative text>
  Takes the rest of the message as the initiative text, calls score_initiative(), and
  returns the Board Pack scoring as a formatted Telegram message.
  Format:
    🔍 INITIATIVE SCORE
    Name: [initiative]
    Upside: [value]  Effort: [value]  Confidence: [level]
    Verdict: GO / NO-GO
    Rationale: [one sentence]
  Also appends the initiative to state/initiative_queue.json for the record.
  If no text follows /score, reply: "Usage: /score <initiative description>"

RULES:
- Follow the exact command registration pattern used for /scheduler and /violations.
- shell=False if any subprocess is involved.
- Per PLAN.md R10 (silence by default): these commands are on-demand only.
  Do not trigger commercial output in any automated message without CEO request.
- Per PLAN.md R5: if score_initiative() returns go_no_go=NO-GO on any live-money
  initiative, the command must append "⚠️ Requires CEO approval before execution."

SUCCESS CRITERIA:
- /commercial returns a formatted response without error
- /score test initiative returns all eight Board Pack fields
- state/initiative_queue.json is updated after /score is called
- All existing commands (/scheduler, /violations, etc.) still work
```

> **→ CODEX REVIEW GATE** — run on modified `telegram_bridge.py` (or `tool_router.py`) before Block 6.
> Check: R10 silence-by-default respected, R5 CEO approval flag present on NO-GO responses,
> shell=False, no secrets logged, existing commands untouched. Full gate in CLAUDE.md.

---

## BLOCK 6 — Tests + Stage G Close

```
Read PLAN.md and CLAUDE.md completely before doing anything.
Blocks 1–5 must be complete before starting this block.

STEP 1 — Write tests for the new commercial module.

Add tests to the existing test suite (study the existing test file structure first —
do not create a new test runner or testing framework).

Tests to add:
  test_finance_report_with_full_data()     — verify correct PNL extraction
  test_finance_report_with_missing_data()  — verify graceful None returns, no exceptions
  test_risk_check_green()                  — drawdown below amber threshold → GREEN
  test_risk_check_amber()                  — drawdown between amber and red → AMBER
  test_risk_check_red()                    — drawdown above red threshold → RED
  test_run_commercial_returns_structure()  — result dict has required keys
  test_initiative_queue_update()           — state/initiative_queue.json updated after /score

STEP 2 — Run the full test suite.
  All previous tests (23/23 passing as of commit e533073) must still pass.
  All new commercial tests must pass.
  Report: X/Y tests passing. If any fail, fix before proceeding.

STEP 3 — Trigger a dry-run.
  Run run_commercial_division() against the current daily brief and confirm:
  - No exceptions raised
  - Result dict structure is correct
  - Status is GREEN, AMBER, or RED (not None, not empty)
  - Report written to reports/commercial_latest.json

STEP 4 — Confirm two consecutive GREEN briefs include commercial data.
  After the next two scheduled daily briefs, confirm reports/phase2_divisions_latest.json
  contains a "commercial" section with status=GREEN in both runs.
  Save these as reports/stage_g_brief_1.json and reports/stage_g_brief_2.json.

STEP 5 — Update PLAN.md.
  Once Steps 1–4 are all verified, update PLAN.md:
  a. In §11 table, change Stage G:
     FROM: 🟡 IN PROGRESS — see §11.2
     TO:   ✅ COMPLETE — [date]. Commercial division GREEN. commit [hash].
  b. In §11 infrastructure list, add:
     - Stage G (Commercial Division): ✅ COMPLETE — [date]. Four sub-functions live.
       /commercial and /score commands active. [N] tests passing. commit [hash].
  c. Update version to 5.4, last updated to today's date.
  d. Update §3 Division status table — Commercial row:
     FROM: PLANNED (Stage G)
     TO:   LIVE (GREEN)
  e. Add footer note: "v5.4 change: Stage G complete. Commercial Division live."

RULES:
- Do not mark Stage G complete until all five steps above are confirmed.
- Do not start Stage E (Research Division) until Stage G shows GREEN in two briefs.
  Per PLAN.md G2: one new division at a time.

SUCCESS CRITERIA:
- All tests passing (previous 23 + new commercial tests)
- reports/commercial_latest.json exists with correct structure
- reports/stage_g_brief_1.json and stage_g_brief_2.json both contain commercial=GREEN
- PLAN.md version 5.4, Stage G = ✅ COMPLETE
- PLAN.md §3 Division status: Commercial = LIVE (GREEN)
```

---

*STAGE_G_PROMPTS.md — AI Holding Company — created 2026-04-15*
*Run one block at a time. Verify success criteria before proceeding to the next block.*
*Next stage after G is complete: Stage E (Research Division) — per PLAN.md critical path.*
