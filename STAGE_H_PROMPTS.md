# Stage H — Holding Board v2 + Board Pack Upgrade
## Claude Code Prompts

**Stage H context (read before starting):**
Stage G complete. Commercial Division live, 45/45 tests passing, commit 1367323.
Codex review clean (8 issues resolved including HIGH inverted-threshold bug).
Stage H is next on the critical path (PLAN.md §11.3).

**What this stage upgrades:**
The CEO layer (Phase 3) currently surfaces non-GREEN KPI items as simple 3-field
approval requests {priority, topic, decision}. Stage H upgrades this to proper
Board Pack items — all 8 fields required by PLAN.md §8, a Dissent agent that files
one objection per item, and Commercial data wired inline so every decision the CEO
sees is fully scored before it arrives.

**Key files to study before writing anything:**
- `crews/holding_ceo.yaml` — current single-agent CEO crew, ceo_board_task template
- `scripts/phase3_holding.py` — focus on:
  - `_build_board_review()` (line ~665) — the function being upgraded
  - `_build_phase3_markdown()` (line ~711) — report renderer to extend
  - `_score_company()` (line ~193) — where Commercial status must be added
  - `_run_ceo_brief()` (line ~521) — understand how divisions_json flows in
  - `_ALLOWED_PHASE3_SUBCOMMANDS` (line ~438) — allowlist to extend
- `scripts/commercial.py` — understand run_commercial_division() output structure
- `PLAN.md §8` — the 8 Board Pack fields, exact names, exact requirements

**Philosophy (per CLAUDE.md — non-negotiable):**
- Minimum change that delivers the upgrade. No structural refactors.
- Do not change existing function signatures.
- No new helpers in utils.py without removing a duplicate.
- shell=False always. No LLM arithmetic.

**Code Review Gate (per CLAUDE.md — after every block):**
Full gate definition in CLAUDE.md → "Code Review Gate". Run after every block
on all files modified. Check style/linting, logic, security. Resolve all issues
before proceeding to the next block.

---

## BLOCK 1 — Dissent Agent + CEO Crew Upgrade

```
Read PLAN.md, CLAUDE.md, and crews/holding_ceo.yaml completely before doing anything.

Edit one file: crews/holding_ceo.yaml

CONTEXT:
The current crew has one agent (holding_ceo) and one task (ceo_board_task).
PLAN.md §8 requires: "Dissent agent must file one objection minimum" on every
Board Pack decision. Add a Dissent agent alongside the existing CEO agent.

CHANGE 1 — Add a second agent entry after holding_ceo:

  - key: "dissent_agent"
    role: "Board Dissent Officer"
    goal: "File at least one substantive objection or counter-argument for every
           Board Pack item proposed. Your job is to stress-test decisions, not to
           block them. Surface the most credible risk the CEO may not have considered."
    backstory: "You represent the critical voice in the boardroom. You are not an
                obstructionist — you are the guardrail. You read every proposed decision
                and ask: what could go wrong, what is being assumed, and what would a
                sceptic say? You file exactly one objection per item, clearly and briefly."
    allow_delegation: false

CHANGE 2 — Add a second task entry after ceo_board_task:

  - key: "dissent_task"
    agent: "dissent_agent"
    description: |
      You are reviewing the Board Pack items produced by the CEO agent.

      Board Pack items:
      {board_pack_json}

      For each item in the list, file one counter-argument or risk that the
      CEO should consider before approving. Be specific — no generic objections.
      Reference the actual topic, metric, or initiative by name.

      Format your output as a JSON list:
      [
        {{"item": "<topic>", "objection": "<one clear sentence>"}},
        ...
      ]

      If there are no Board Pack items (empty list), return an empty JSON list [].
      Do not invent items to object to.
    expected_output: |
      JSON list of objections, one per Board Pack item. Empty list if no items.

CHANGE 3 — Update manager_agent to reflect the two-agent structure:
  The crew now has two agents. The holding_ceo agent produces the board pack;
  the dissent_agent reviews it. Set:
    manager_agent: "holding_ceo"
  (unchanged — CEO agent coordinates the crew)

RULES:
- Match indentation and style of the existing crew YAML exactly.
- Do not change the ceo_board_task description or expected_output.
- Do not add a third agent or task.
- verbose: false (unchanged)

SUCCESS CRITERIA:
- crews/holding_ceo.yaml is valid YAML
- Two agents defined: holding_ceo and dissent_agent
- Two tasks defined: ceo_board_task and dissent_task
- dissent_task references {board_pack_json} template variable
- No existing ceo_board_task content altered
```

> **→ CODEX REVIEW GATE** — run on `crews/holding_ceo.yaml` before Block 2.
> Check: valid YAML, consistent structure vs other crew files, no duplicate keys,
> dissent_task template var {board_pack_json} correctly formatted. Full gate in CLAUDE.md.

---

## BLOCK 2 — Board Pack 8-Field Upgrade in phase3_holding.py

```
Read PLAN.md §8, CLAUDE.md, and scripts/phase3_holding.py completely before doing anything.
Block 1 must be complete before starting this block.

Edit one file: scripts/phase3_holding.py

CONTEXT:
The current _build_board_review() function (line ~665) produces a list of approval items
with only 3 fields: {priority, topic, decision}. PLAN.md §8 requires all 8 fields per item.
Upgrade this function to produce the full Board Pack format.

CHANGE 1 — Upgrade _build_board_review() to 8-field output.

The function signature stays the same:
  def _build_board_review(company_scorecard, divisions) -> dict

The returned approval item structure changes from:
  {"priority": str, "topic": str, "decision": str}

To the full 8-field Board Pack format (PLAN.md §8):
  {
    "rationale":          str,   # why this item is being surfaced now
    "expected_upside":    str,   # quantified where possible; "n/a" if not applicable
    "effort_cost":        str,   # time/compute/money estimate; "n/a" if not applicable
    "confidence":         str,   # "High" | "Medium" | "Low" + one-line reason
    "owner":              str,   # named division (e.g. "trading", "commercial", "websites")
    "deadline":           str,   # ISO date string or "immediate" for RED items
    "dissent":            str,   # placeholder — filled in by dissent_agent in Block 3
    "measurement_plan":   str,   # how success will be measured post-action
    "priority":           str,   # "RED" | "AMBER" (kept for backward compat)
    "topic":              str,   # metric or initiative name (kept for backward compat)
  }

Population rules (Python only — no LLM calls inside this function):
- rationale: derive from item.get("action") and status — e.g.
  "KPI {metric} is {status} (actual={actual}, target={target}). Immediate review required."
- expected_upside: "Restores {metric} to target ({target})" for KPI items
- effort_cost: "n/a" — to be refined by Commercial scoring on /score command
- confidence: "Medium — derived from telemetry; LLM scoring not yet applied"
- owner: derive from which division the item came from (company-level → "holding",
  trading items → "trading", websites → "websites", commercial → "commercial")
- deadline: datetime.now(timezone.utc).date().isoformat() for RED; "+7d" for AMBER
- dissent: "PENDING — dissent_agent review required"  ← placeholder always
- measurement_plan: "Monitor {metric} in next daily brief. GREEN for 2 consecutive runs."

CHANGE 2 — Add Commercial division items to _build_board_review().
The function currently only reads company_scorecard and divisions.
Add a third optional parameter: commercial_result: dict | None = None

If commercial_result is not None and commercial_result.get("status") != "GREEN":
  Append a Board Pack item sourced from the commercial risk dict:
    topic: "Commercial: " + first exposure_flag if any, else "Commercial risk check"
    owner: "commercial"
    rationale: commercial_result.get("risk", {}).get("risk_verdict", "n/a")
    priority: commercial_result.get("status", "AMBER")

CHANGE 3 — Update all callers of _build_board_review() in phase3_holding.py
to pass commercial_result where available. Check every call site and add the
argument. If commercial_result is not available at a call site, pass None.

RULES:
- Do not add LLM calls inside _build_board_review() — all field values derived
  from existing data in Python. The dissent field is always a placeholder here;
  the dissent_agent fills it in the crew run.
- Keep {priority} and {topic} fields — they are used in _build_phase3_markdown().
- Backward-compatible: existing callers that don't pass commercial_result still work.

SUCCESS CRITERIA:
- _build_board_review() returns items with all 10 keys (8 Board Pack + priority + topic)
- "dissent" field is always "PENDING — dissent_agent review required" from this function
- commercial_result=None is handled gracefully (no exception)
- python -c "from phase3_holding import _build_board_review; print('ok')" exits 0
- All existing tests still pass
```

> **→ CODEX REVIEW GATE** — run on `scripts/phase3_holding.py` (changed functions only) before Block 3.
> Check: PEP 8, all new dict keys present on every code path, no LLM calls inside
> _build_board_review(), commercial_result=None handled safely, no off-by-one on
> the approvals[:10] slice with new field structure. Full gate in CLAUDE.md.

---

## BLOCK 3 — Commercial Data into CEO Brief + board_pack Mode

```
Read PLAN.md, CLAUDE.md, and scripts/phase3_holding.py completely before doing anything.
Blocks 1 and 2 must be complete before starting this block.

Edit one file: scripts/phase3_holding.py

CONTEXT:
Two additions: (1) wire Commercial division status into _score_company() so the company
scorecard reflects Commercial health, and (2) add a new "board_pack" run mode that
triggers the full Holding Board v2 flow including the Dissent agent.

CHANGE 1 — Wire Commercial into _score_company().
Locate _score_company() (line ~193). It currently reads Trading and Websites division
data. Add Commercial:
  - Pull commercial status from the divisions payload where division == "commercial"
  - If commercial status is RED or AMBER, add it to the company scorecard items list
    with metric="commercial_health", actual=status, target="GREEN"
  - Include commercial status in the _status_worst() calculation that determines
    overall company status
  - If commercial data is missing entirely, degrade gracefully (do not raise)

CHANGE 2 — Add "board_pack" as a valid mode in _run_ceo_brief().
Locate _run_ceo_brief() (line ~521). It currently handles modes: "heartbeat" and
"board_review". Add "board_pack" mode:
  - "board_pack" runs the full crew from holding_ceo.yaml including the dissent_task
  - It passes {board_pack_json} to the dissent_task template — serialize the
    board_review["approvals"] list as JSON for this template variable
  - After the dissent_task runs, merge the dissent objections back into the
    board_review approvals: for each dissent item matching an approval topic,
    replace the "dissent" placeholder with the actual objection text
  - If the dissent_task returns malformed JSON or fails, set dissent field to
    "Dissent agent unavailable — manual review required" (do not raise)

CHANGE 3 — Update _build_phase3_markdown() to render the new 8-field format.
Locate the board_review section in _build_phase3_markdown() (line ~770 approx).
Currently renders: [{priority}] {topic}: {decision}
Upgrade to render all 8 Board Pack fields for each approval item:

  ## Board Pack
  ### [{priority}] {topic}
  - **Rationale:** {rationale}
  - **Upside:** {expected_upside}
  - **Effort/Cost:** {effort_cost}
  - **Confidence:** {confidence}
  - **Owner:** {owner}
  - **Deadline:** {deadline}
  - **Dissent:** {dissent}
  - **Measurement:** {measurement_plan}

Render this for mode == "board_review" AND mode == "board_pack".
Fallback gracefully if any field is missing (use "n/a").

CHANGE 4 — Add board_pack to _ALLOWED_PHASE3_SUBCOMMANDS (line ~438).
Add entry:
  "run_holding_board_pack": {
    "args": ["--force"],
    "required": [],
  }
And add the corresponding subcommand to tool_router.py that calls
run_phase3_holding(config, mode="board_pack", force=True/False).

RULES:
- No new functions — extend existing ones with the minimum change.
- All JSON serialization uses json.dumps() with Python stdlib — no new imports.
- Dissent merge is best-effort: mismatch in topic string → log a warning, keep placeholder.
- Do not change heartbeat or board_review mode behaviour.

SUCCESS CRITERIA:
- python scripts/tool_router.py run_holding --mode board_pack runs without exception
- Output JSON contains board_review.approvals with all 10 keys per item
- Output markdown renders all 8 Board Pack fields per approval item
- "dissent" field in output is NOT "PENDING" if dissent_agent ran successfully
- Commercial health appears in company scorecard when status != GREEN
- All existing tests still pass
```

> **→ CODEX REVIEW GATE** — run on `scripts/phase3_holding.py` and `scripts/tool_router.py` before Block 4.
> Check: no LLM calls in _score_company(), JSON serialization is stdlib only,
> dissent merge failure path always sets a non-empty string (never leaves raw exception),
> board_pack mode in allowlist matches tool_router subcommand name exactly,
> shell=False on any new subprocess. Full gate in CLAUDE.md.

---

## BLOCK 4 — MA Gate: Block Incomplete Board Pack Items

```
Read PLAN.md §5 and §8, CLAUDE.md, and scripts/telegram_bridge.py (or tool_router.py —
check which file handles MA message routing) before doing anything.
Blocks 1–3 must be complete before starting this block.

CONTEXT:
PLAN.md §8: "MA blocks any decision missing a field from reaching the CEO."
Currently there is no validation gate — board items with missing fields pass through.
Add a validation function and wire it into the Telegram message routing.

CHANGE 1 — Add _validate_board_pack_item() to phase3_holding.py.

def _validate_board_pack_item(item: dict) -> list[str]:
    """Return list of missing field names. Empty list means item is valid."""
    required = [
        "rationale", "expected_upside", "effort_cost", "confidence",
        "owner", "deadline", "dissent", "measurement_plan",
    ]
    missing = []
    for field in required:
        value = item.get(field, "")
        if not value or str(value).strip() in ("", "n/a", "PENDING — dissent_agent review required"):
            # "PENDING" dissent is only acceptable if dissent_agent was unavailable
            if field == "dissent" and "unavailable" in str(value):
                continue
            missing.append(field)
    return missing

Note: "n/a" is acceptable for effort_cost and expected_upside on non-initiative items.
Refine the check: only flag "n/a" as missing for rationale, owner, deadline,
dissent, and measurement_plan. effort_cost and expected_upside may legitimately be "n/a".

CHANGE 2 — Wire the gate into the board_pack report generation.
In _build_board_review() (or in the board_pack mode of _run_ceo_brief()), after
building the approvals list, run each item through _validate_board_pack_item().
If missing fields are found:
  - Do NOT remove the item from the approvals list
  - Add a "validation_warnings" key to the item: list of missing field names
  - Add a top-level "gate_blocked" key to the board_review dict: True if any
    item has validation_warnings, False otherwise

CHANGE 3 — Surface the gate status in the Telegram board_pack command response.
In the Telegram handler for /board_pack (or run_holding_board_pack):
  - If board_review.get("gate_blocked") is True:
    Prefix the response with:
    "⚠️ MA GATE: Board Pack contains incomplete items. Missing fields listed.
     CEO review blocked until resolved."
    Then list each incomplete item and its missing fields.
  - If gate_blocked is False: deliver normally.

RULES:
- _validate_board_pack_item() is a pure function — no side effects, no I/O.
- The gate warns but does not silently drop items. The CEO always sees what exists.
- Do not apply this gate to heartbeat or board_review modes — board_pack only.
- Per PLAN.md §5 rule 9: "Any new initiative without all 5 KPI fields — see §8"
  is an MA escalation trigger. This gate is the automated enforcement of that rule.

SUCCESS CRITERIA:
- _validate_board_pack_item() returns empty list for a fully populated item
- _validate_board_pack_item() returns correct missing fields for a partial item
- board_review dict contains "gate_blocked": True when any item is incomplete
- Telegram response for incomplete board pack starts with ⚠️ MA GATE prefix
- Telegram response for complete board pack delivers normally with no gate message
- All existing tests still pass
```

> **→ CODEX REVIEW GATE** — run on `scripts/phase3_holding.py` and `scripts/telegram_bridge.py` before Block 5.
> Check: _validate_board_pack_item() handles missing keys without raising,
> gate_blocked key always present in board_review dict (True or False, never None),
> Telegram handler cannot surface raw exception text to CEO,
> no shell=False violations. Full gate in CLAUDE.md.

---

## BLOCK 5 — Tests + Stage H Close

```
Read PLAN.md, CLAUDE.md, and the existing test suite before doing anything.
Blocks 1–4 must be complete before starting this block.

STEP 1 — Add tests for Stage H changes.
Study the existing test file structure first. Add tests to the existing suite —
do not create a new test runner.

Tests to add:

  # Board Pack 8-field format
  test_board_pack_item_has_all_fields()
    — _build_board_review() output items contain all 10 keys (8 BP + priority + topic)

  test_board_pack_dissent_placeholder()
    — dissent field is "PENDING..." when dissent_agent has not run

  test_board_pack_commercial_included()
    — when commercial_result status=AMBER, an item appears with owner="commercial"

  test_board_pack_commercial_none_safe()
    — _build_board_review(scorecard, divisions, commercial_result=None) does not raise

  # Validation gate
  test_validate_full_item_passes()
    — _validate_board_pack_item() returns [] for a fully populated item

  test_validate_missing_dissent_flagged()
    — "PENDING..." dissent returns ["dissent"] in missing list

  test_validate_na_allowed_for_effort_cost()
    — "n/a" in effort_cost does NOT appear in missing list

  test_gate_blocked_true_when_incomplete()
    — board_review["gate_blocked"] is True when any item has validation_warnings

  test_gate_blocked_false_when_complete()
    — board_review["gate_blocked"] is False when all items pass validation

  # Dissent agent integration
  test_dissent_merge_replaces_placeholder()
    — after dissent_task runs, "PENDING" replaced with actual objection text

  test_dissent_merge_failure_safe()
    — malformed dissent_task output sets "unavailable" string, does not raise

STEP 2 — Run full test suite. All tests must pass.
  Report: X/Y tests passing. If any fail, fix before proceeding.

STEP 3 — Run board_pack mode end-to-end.
  python scripts/tool_router.py run_holding_board_pack
  Confirm:
  - Output JSON contains board_review with gate_blocked key
  - At least one approval item has all 10 keys populated
  - If dissent_agent ran: dissent field is not "PENDING"
  - Markdown output renders all 8 Board Pack fields per item

STEP 4 — Two consecutive GREEN board_pack runs.
  After two scheduled runs, confirm:
  - reports/phase3_holding_latest.json contains board_review.gate_blocked = false
  - Save as reports/stage_h_brief_1.json and reports/stage_h_brief_2.json

STEP 5 — Update PLAN.md.
  Once Steps 1–4 are verified, update PLAN.md:
  a. In §11 table, change Stage H:
     FROM: 🟡 IN PROGRESS — see §11.3
     TO:   ✅ COMPLETE — [date]. Board Pack v2 live. commit [hash].
  b. In §11 infrastructure list, add:
     - Stage H (Holding Board v2): ✅ COMPLETE — [date]. 8-field Board Pack format.
       Dissent agent live. Commercial wired. MA gate enforcing. [N] tests passing. commit [hash].
  c. Update HANDOFF.md — add Stage H complete, Stage E next.
  d. Update version to 5.5, last updated to today.
  e. Footer: "v5.5 change: Stage H complete. Holding Board v2 live."

RULES:
- Do not mark Stage H complete until all four steps verified.
- Per PLAN.md G2: do not start Stage E (Research Division) until Stage H shows
  two GREEN board_pack runs.

SUCCESS CRITERIA:
- All previous tests + new Stage H tests passing (target ≥ 56 tests)
- board_review in JSON output has gate_blocked key on every run
- Two consecutive board_pack reports saved as stage_h_brief_1/2.json
- PLAN.md version 5.5, Stage H = ✅ COMPLETE
```

> **→ CODEX REVIEW GATE** — final retrospective review across all Stage H files:
> `crews/holding_ceo.yaml`, `scripts/phase3_holding.py`, `scripts/tool_router.py`,
> `scripts/telegram_bridge.py`.
> Check all three categories. Resolve all issues. Confirm N issues found, N resolved, CLEAN.
> Record in commit message: "Codex review: N issues resolved."

---

*STAGE_H_PROMPTS.md — AI Holding Company — created 2026-04-15*
*Run one block at a time. Codex review gate after every block. Full gate in CLAUDE.md.*
*Next stage after H is complete: Stage E (Research Division) — per PLAN.md critical path.*
