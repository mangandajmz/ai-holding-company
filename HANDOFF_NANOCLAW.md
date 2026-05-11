# NanoClaw Handoff — Dispatch Continuation

**Date:** 2026-05-10
**Branch:** `claude/nanoclaw-feature` (main worktree, not a `.claude/worktrees/*` worktree)
**Worktree path:** `C:/Users/james/OneDrive/Documents/Claude/Projects/AI Holding Company/ai-holding-company`
**Head:** `66cccdf`
**PR:** [mangandajmz/ai-holding-company#10](https://github.com/mangandajmz/ai-holding-company/pull/10) — open, awaiting review
**Tests:** 28 passing (was 21 at prior handoff)
**Companion doc:** `NANOCLAW_TEST_REPORT.md` at repo root — full system overview, packet examples, file map

---

## What this branch does

Brings the persona conversational layer from "shadow-only, deterministic answers" to "production-ready Ollama-backed live answers, gated by an explicit acceptance ratchet". Live model output never reaches the owner unless it passes `verify_verbalizer_output()`. On any failure the deterministic fallback answers. Per-persona config flag controls promotion; no auto-promotion.

R1 (Ollama only, no cloud APIs) is preserved. No new dependencies. Stdlib `urllib` only.

---

## Commits on this branch (latest first)

| Commit | Subject |
|---|---|
| `63319e2` | feat: nanoclaw acceptance gate config + nanoclaw_status CLI |
| `349ecce` | feat: gate nanoclaw_live behind config mode with verifier fallback |
| `66dfc08` | feat: add nanoclaw_live verbalizer that calls local Ollama |
| `1d8d3e1` | fix: drop urgency framing when chief-of-staff lead evidence is GREEN |
| `9b047c0` | (prior handoff state — shadow pipeline complete) |

Run `git log 9b047c0..HEAD --stat` for the full diff scope.

---

## Files touched

| File | Role on this branch |
|---|---|
| `scripts/persona_verbalizer.py` | Added `nanoclaw_live_verbalize()`, `_effective_nanoclaw_mode()`, `_append_live_log()`. Extended `run_verbalizers()` with live-mode branch + verifier gate + fallback. GREEN guard in `_chief_status()`. |
| `scripts/persona_router.py` | `answer_persona()` accepts new optional `full_config` kwarg and passes it to `run_verbalizers`. |
| `scripts/tool_router.py` | `persona_chat` forwards `full_config=config`. New `nanoclaw_status` subcommand. |
| `scripts/nanoclaw_status.py` | New module — reads live log, computes per-persona accept rate and `meets_gate`. |
| `config/projects.yaml` | New `conversation.nanoclaw.promotion` (window, min_accept_rate), `personas` map (all `shadow`), `live_log_path`. |
| `tests/test_persona_router.py` | +4 tests (GREEN guard, live success, live fallback on empty, live unreachable). |
| `tests/test_nanoclaw_status.py` | New file — 3 tests (accept rate, gate condition, live log append). |

---

## How to run / verify

```bash
cd "C:/Users/james/OneDrive/Documents/Claude/Projects/AI Holding Company/ai-holding-company"

# All NanoClaw-relevant tests
python -m pytest tests/test_persona_router.py tests/test_tool_router_ask_company.py tests/test_nanoclaw_status.py -q
# Expect: 28 passed

# Smoke test the status CLI (will show zero traffic until live mode is enabled for at least one persona)
python scripts/tool_router.py nanoclaw_status
```

---

## Where we are in the plan

The full plan is described in chat above and reproduced here for the cold reader.

**Step 0 — Polish deterministic floor.** ✅ Done (`1d8d3e1`). GREEN lead evidence no longer triggers "I would focus there first".

**Step 1 — `nanoclaw_live` provider.** ✅ Done (`66dfc08`). `nanoclaw_live_verbalize(packet, config)` POSTs the packet to `{phase2.ollama_base_url}/api/generate` with `{phase2.ollama_model}`. Single 20s timeout. No retries. No streaming. Returns `{"answer": "", ...}` on any failure so the verifier rejects it.

**Step 2 — Wire the gate.** ✅ Done (`349ecce`). `run_verbalizers` resolves an effective mode per persona (`conversation.nanoclaw.personas[<persona>]` beats global `conversation.nanoclaw.mode`). If effective mode is `live`: call live, verify, use it if accepted, else use deterministic_fallback (tagged with `nanoclaw_live_rejected_reason`). Shadow inbox/outbox plumbing unchanged.

**Step 3 — Acceptance gate config + status CLI.** ✅ Done (`63319e2`). Per-attempt records appended to `state/nanoclaw_live_log.jsonl`. `nanoclaw_status` CLI prints per-persona accept rate over the last `window` records and a `meets_gate` flag (`window_size >= window AND accept_rate >= min_accept_rate`). No auto-promotion.

**Step 4 — Run shadow at volume.** 🔜 Not code. Owner uses Telegram normally; eventually flips one persona to `live` and watches `nanoclaw_status` until `meets_gate: true` for Chief of Staff.

**Step 5 — Promote Chief of Staff to live.** 🔜 Config flip only:
```yaml
conversation:
  nanoclaw:
    personas:
      chief-of-staff: "live"
```
Reversible — flip back to `shadow` instantly if accept rate dips.

**Step 6 — Promote remaining personas one at a time.** 🔜 Order: Growth Lead → Editorial Lead → Engineering/Ops → Support Lead → Quant Ops → Risk Officer (last, because its outputs carry block/objection language).

**Step 7 — Tighten the verifier.** 🔜 Code work. `verify_verbalizer_output()` currently rejects on empty answer or non-empty `unsupported_claims`. Once real model traffic accumulates, harden it: detect invented numbers, invented persona names, invented approvals, hallucinated dates. The verifier is the system's main quality lever post-live.

**Step 8 — Retire shadow as a config option.** 🔜 Drop the `shadow` branch from `run_verbalizers` once all 8 personas have lived in `live` for a quarter. Shadow inbox/outbox logs remain as the audit trail.

---

## What dispatch should do next (priority order)

1. **Watch PR [#10](https://github.com/mangandajmz/ai-holding-company/pull/10) through review and merge.** Address review feedback on this branch; do not rebase or force-push unless the reviewer asks. After merge, delete the remote branch and update the head reference in this handoff if any follow-up work continues.

2. **Verify Ollama is reachable on the host** that runs the Telegram bridge:
   ```bash
   curl -s http://127.0.0.1:11434/api/tags | head -c 200
   ```
   If empty or refused, Step 4 cannot start.

3. **Skip ahead to Step 7 (verifier tightening) if owner wants more confidence before promoting any persona.** Concrete starter checks to add to `verify_verbalizer_output()`:
   - Reject answers containing numbers that do not appear (textually or as numerals) anywhere in the truth packet.
   - Reject answers containing persona slugs other than `packet["persona"]` (prevents one persona impersonating another).
   - Reject answers longer than ~600 characters (current personas should be terse).
   - All new rejection paths must be tested with both accept and reject cases.

4. **Do not edit Step 5/6 prematurely.** Promotion is a single YAML edit; no code change needed. The plan deliberately keeps it that way.

---

## Hard constraints (from CLAUDE.md, do not violate)

- **R1: Ollama only.** No cloud inference. `nanoclaw_live_verbalize` already obeys this — do not add OpenAI/Anthropic adapters.
- **R11: No OpenClaw.** Telegram bridge is the sole automation interface.
- **shell=False** on every subprocess call. None added on this branch; do not add any.
- **No overengineering.** Do not introduce a "provider registry" or abstract base class to support hypothetical future models. One provider, one HTTP call.
- **Code Review Gate.** Every block of work passes Codex review before the next block starts. This branch's 4 commits are individually small and reviewable.

---

## Known noise to ignore

- Submodules `finance_web_page` and `mt5-agentic-desk` show pointer drift in `git status`. Memory note `project_property_promotion.md` says these are unpromoted properties; their drift is not a blocker on this branch.
- The local main worktree's `git status -u` also lists many `.claude/worktrees/*/` and `.gstack/`, `projects/` untracked directories. Ignore — these are sibling worktrees and tooling state, not work artifacts.

---

## One non-obvious thing the next agent should know

`run_verbalizers` takes BOTH `config=` (the `conversation.*` slice) and `full_config=` (the whole `projects.yaml` dict). The split exists because `nanoclaw_live_verbalize` needs `phase2.ollama_model` and `phase2.ollama_base_url`, which sit outside the conversation slice. `answer_persona` forwards both. `tool_router.py:persona_chat` passes them as `conversation_config=config.get("conversation", {})` and `full_config=config`. If you write a new caller, do the same.

---

*Written 2026-05-10 by Claude after PR #10 opened (head `66cccdf`). End of handoff.*
