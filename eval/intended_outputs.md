# Intended Output Specification — CEO-Standard Telegram Responses
# AI Holding Company — Manganda LTD

> This document defines the **golden standard** for every Telegram command response.
> It is the source of truth for the eval harness (`tests/test_response_quality.py`).
> All examples use realistic mock data. Real output must match this structure.

---

## Design Principles

**Who receives these messages:** The CEO on a mobile phone, in Telegram.

**Format constraints:**
- Plain text only (no Telegram MarkdownV2 parse_mode)
- Max 3,900 characters per message
- Rendered in a monospace-adjacent sans-serif font on mobile

**Quality bar — a response passes CEO standard when:**
1. Status is visible in the first 2 lines without scrolling
2. Every number has context: actual vs target, not just raw values
3. Traffic lights use emoji (🔴🟡🟢), not `[RED]`/`[AMBER]`/`[GREEN]`
4. Actions are specific: verb + subject + deadline, not generic advice
5. No raw JSON, no key=value noise, no debug output visible
6. Closes with a single next-step command hint, not a menu of 6 options

---

## Scoring Rubric (used by eval harness)

Each response is scored 0–10 against these weighted criteria:

| # | Criterion | Weight | Pass Condition |
|---|-----------|--------|----------------|
| 1 | Header — company + timestamp | 1 | Contains company name and UTC datetime |
| 2 | Exec summary line | 2 | First 3 lines contain overall status emoji + one-liner |
| 3 | Metrics have context | 2 | Each number has target or variance alongside it |
| 4 | Traffic light emoji | 1 | Uses 🔴/🟡/🟢, not `[RED]`/`[AMBER]`/`[GREEN]` |
| 5 | No raw JSON / debug noise | 1 | No `{`, `"ok":`, `return_code`, `rc=`, `elapsed_ms` visible |
| 6 | Actions are owner-assigned | 2 | Actions name a division or owner, not generic text |
| 7 | Single focused CTA at end | 1 | Ends with ≤1 command suggestion, not a list |

**Pass threshold:** ≥ 8 / 10

---

## Command: `/status`

**Purpose:** Quick daily pulse — are we up, trading, and on target?
**SLA:** ≤ 5 seconds (uses cached brief)
**Max length:** 800 characters

### INTENDED OUTPUT

```
─────────────────────────────
MANGANDA LTD  ·  Daily Pulse
17 Apr 2026  08:14 UTC
─────────────────────────────
🟡 AMBER  —  2 items need attention

TRADING
  PnL today    +$156.78  (MTD: +$279.98)
  Trades           47    (target ≥40 ✓)
  Errors            2    (threshold: ≤3 ✓)

INFRASTRUCTURE
  Websites     2 / 2 UP
  freeghosttools    145ms
  freetraderhub     203ms

ALERTS  (2)
  ⚠ Max drawdown approaching threshold
  ⚠ Monthly PnL growth below 10% target

→ /brief for full CEO scorecard
```

### Criteria check
- ✅ Status visible line 4 (`🟡 AMBER`)
- ✅ PnL has MTD context
- ✅ Trades show target inline
- ✅ No raw JSON
- ✅ Single CTA at end

### Current gap
Current output: `Daily brief: ok=true, skipped=false` — fails criteria 2, 3, 4, 7.

---

## Command: `/brief`  (CEO Heartbeat)

**Purpose:** Full company scorecard — CEO morning review.
**SLA:** ≤ 120 seconds (Phase 3 crew run)
**Max length:** 3,200 characters

### INTENDED OUTPUT

```
══════════════════════════════
MANGANDA LTD  ·  CEO Heartbeat
17 Apr 2026  08:15 UTC  ·  heartbeat
══════════════════════════════
🟡 AMBER — 1 RED  ·  2 AMBER  ·  2 GREEN

COMPANY KPIs
🔴 Monthly PnL growth   8.5%  vs  ≥10.0%  (−1.5pp) → REVIEW
🟡 Max drawdown         4.2%  vs  ≤3.0%   (+1.2pp) → WATCH
🟢 Website uptime     100.0%  vs  ≥99.9%  (+0.1pp)
🟢 Division GREEN       66.7% vs  ≥66.7%  (on target)

DIVISIONS
Trading    🟡  —  PnL growth 8.5% vs 10% target
Websites   🟢  —  All sites up, latency nominal

DECISIONS REQUIRED  (1 RED · 1 AMBER)
1. 🔴 Monthly PnL: Review risk allocation
   Owner: Trading  ·  Deadline: today
2. 🟡 Max drawdown: Tighten stop-loss threshold
   Owner: Trading  ·  Deadline: +7 days

Report: reports/phase3_holding_latest.md
→ /board review to formalise approvals
```

### Criteria check
- ✅ Status line 4: `🟡 AMBER — 1 RED · 2 AMBER · 2 GREEN`
- ✅ Every KPI: actual vs target vs variance
- ✅ Traffic light emoji per KPI line
- ✅ Decisions are numbered, owner-assigned, deadline-stamped
- ✅ Single CTA: `/board review`
- ✅ No `return_code`, `elapsed_ms`, `ok=`

### Current gap
Current: `- [RED] Monthly PnL growth: actual=8.5% target=>=10.0% variance=-1.5%`
Missing: emoji, decision block, owner, deadline.

---

## Command: `/board review`

**Purpose:** Formal approval matrix — CEO signs off on priority items.
**SLA:** ≤ 120 seconds
**Max length:** 3,500 characters

### INTENDED OUTPUT

```
══════════════════════════════
MANGANDA LTD  ·  Board Review
17 Apr 2026  08:16 UTC
══════════════════════════════
🟡 AMBER  ·  2 items for approval

APPROVAL ITEMS

1. 🔴 Monthly PnL Growth  [Trading]
   Issue:   MTD 8.5% vs 10% target; 1.5pp shortfall
   Upside:  Restores growth trajectory; est +$180 MTD
   Effort:  Low — parameter adjustment, no deployment
   Confidence: Medium
   Owner:   Trading Division
   Deadline: 17 Apr 2026  (today — RED)
   Dissent: PENDING review
   Measure: GREEN for 2 consecutive daily briefs

2. 🟡 Max Drawdown  [Trading]
   Issue:   4.2% actual vs 3.0% cap; approaching limit
   Upside:  Prevents forced halt; protects capital base
   Effort:  Low — stop-loss threshold update
   Confidence: High
   Owner:   Trading Division
   Deadline: 24 Apr 2026  (+7 days)
   Dissent: PENDING review
   Measure: Drawdown ≤3.0% next 3 runs

─────────────────────────────
Approve, defer, or reject each item explicitly.
Board pack saved: reports/phase3_holding_latest.md
→ /brief to re-run scorecard after changes
```

### Criteria check
- ✅ Numbered approval items, not a wall of bullets
- ✅ All 8 board pack fields visible per item
- ✅ Dissent placeholder explicit (`PENDING review`)
- ✅ Deadline formatted as human date, not ISO
- ✅ Measure is specific and time-boxed
- ✅ Gate block message would replace approval block if validation fails

### Gate-blocked variant (when fields incomplete)

```
══════════════════════════════
MANGANDA LTD  ·  Board Review
17 Apr 2026  08:16 UTC
══════════════════════════════
🔴 GATE BLOCKED — CEO review cannot proceed

Incomplete items (fix before re-running):
  • Monthly PnL Growth: missing measurement_plan, dissent
  • Max Drawdown: missing expected_upside

→ /brief to force a fresh scorecard run
```

---

## Command: `/divisions [all]`

**Purpose:** Division-level operational heartbeat.
**SLA:** ≤ 90 seconds (Phase 2 crews)
**Max length:** 2,000 characters

### INTENDED OUTPUT

```
══════════════════════════════
MANGANDA LTD  ·  Divisions
17 Apr 2026  08:17 UTC
══════════════════════════════
PnL $279.98  ·  Trades 47  ·  Sites 2/2 UP

TRADING  🟡 AMBER
  🔴 PnL growth   8.5%  vs  ≥10.0%  (−1.5pp)
  🟢 Win rate    62.0%  vs  ≥55.0%
  Action: Review risk allocation today

WEBSITES  🟢 GREEN
  🟢 Uptime     100.0%  vs  ≥99.9%
  🟢 Latency      174ms avg (threshold ≤500ms)
  No action required

→ /brief for CEO scorecard  ·  /bot mt5_desk health
```

### Criteria check
- ✅ Division header with emoji status
- ✅ KPIs with target inline
- ✅ Per-division action (or explicit "No action required")
- ✅ Compact CTA at end

---

## Command: `/bot <id> health`

**Purpose:** Single bot liveness and connectivity check.
**SLA:** ≤ 10 seconds
**Max length:** 400 characters

### INTENDED OUTPUT

```
MT5 DESK  ·  Health Check
17 Apr 2026  08:18 UTC
──────────────────────
🟢 CONNECTED  ·  rc=0  ·  1.2s

Last PnL:   +$156.78
Trades:     47 today
Errors:     0

→ /bot mt5_desk report for full session detail
```

### Current gap
Current: `Bot command: {"ok": true, "bot_id": "mt5_desk", "command_key": "health", "return_code": 0, "elapsed_ms": 1243}`
Shows raw JSON. Fails criteria 5.

---

## Command: `/bot <id> report`

**Purpose:** Full session report for a trading bot.
**SLA:** ≤ 20 seconds
**Max length:** 1,200 characters

### INTENDED OUTPUT

```
MT5 DESK  ·  Session Report
17 Apr 2026  08:19 UTC
──────────────────────
🟢 Session active  ·  Runtime 4h 12m

PERFORMANCE
  PnL today    +$156.78  (MTD +$279.98)
  Trades           47    (Win rate 62%)
  Max drawdown    2.1%   (cap 3.0% ✓)

TOP TRADES
  EURUSD   +$89.20   09:14 → 10:03
  GBPUSD   +$43.10   11:22 → 11:58

RISK FLAGS
  None

→ /bot mt5_desk logs 50 for raw log tail
```

---

## Command: `/bot <id> logs [N]`

**Purpose:** Tail and summarise recent bot log lines.
**SLA:** ≤ 5 seconds
**Max length:** 800 characters

### INTENDED OUTPUT

```
MT5 DESK  ·  Log Summary  (last 120 lines)
17 Apr 2026  08:20 UTC
──────────────────────
🟢 No errors  ·  2 trades logged

Last entry:  2026-04-17 08:19:43
Last PnL:   +$156.78
Last trade:  EURUSD long 0.1 lot

──────────────────────
[08:15:12] Trade opened: EURUSD long 0.1
[08:19:43] Trade closed: EURUSD +89.20 pips

→ /bot mt5_desk report for structured summary
```

---

## Command: `/site <id>`

**Purpose:** Instant website liveness check.
**SLA:** ≤ 3 seconds
**Max length:** 200 characters

### INTENDED OUTPUT

```
freeghosttools.com
🟢 UP  ·  145ms  ·  HTTP 200
17 Apr 2026  08:21 UTC
```

### Down variant

```
freetraderhub.com
🔴 DOWN  ·  timeout after 10s  ·  HTTP —
17 Apr 2026  08:21 UTC
⚠ Alert logged — check hosting
```

### Current gap
Current: `Website freeghosttools: UP status=200 latency=145ms`
Functional but lacks emoji, date, and domain name format.

---

## Command: Freetext NL Query

**Example inputs:** `"how is trading doing?"`, `"any issues today?"`, `"what's our PnL?"`
**SLA:** ≤ 15 seconds
**Max length:** 600 characters

### INTENDED OUTPUT  (for "how is trading doing?")

```
Trading  ·  Current status
──────────────────────
🟡 AMBER  —  PnL below target

MTD PnL:  +$279.98  (target +$400+ for pace)
Drawdown: 4.2%  (approaching 3% cap)
Trades:   47 today  ·  Win rate 62%

Relevant context from memory:
  "Risk reduced after Apr 14 volatility event"

→ /brief for full CEO view
```

---

## Command: `/help`

**Purpose:** Orientation for CEO — what can I ask?
**SLA:** < 100ms
**Max length:** 900 characters

### INTENDED OUTPUT

```
MANGANDA LTD  ·  CEO Commands
──────────────────────────────
DAILY OPERATIONS
  /status          Quick pulse (cached, instant)
  /brief           CEO heartbeat — full scorecard
  /divisions all   Division operational review

APPROVALS
  /board review    Approval matrix (formal)
  /board pack      Full 8-field board pack

TRADING BOTS
  /bot mt5_desk health     Connectivity check
  /bot mt5_desk report     Session P&L report
  /bot mt5_desk logs 50    Last 50 log lines

WEBSITES
  /site freeghosttools      Live ping
  /site freetraderhub       Live ping

MEMORY
  /note <text>    Save a directive
  /memory <q>     Search past context

──────────────────────────────
Observer mode: ON  (execute blocked)
→ Start with /brief
```

### Current gap
Current: plain text list with no grouping or hierarchy. All commands at same indent level.

---

## Error Response Standard

All errors must follow this format — no stack traces, no internal details:

```
⚠ Command failed: <what was attempted>
Reason: <one plain-English sentence>
→ <recovery command or next step>
```

### Examples

**Unknown bot ID:**
```
⚠ Command failed: /bot unknown_bot health
Reason: 'unknown_bot' is not a configured bot.
→ /help to see available bot IDs
```

**Observer mode block:**
```
⚠ Blocked: execute requires confirmation
Reason: Observer mode is ON — no live trades.
→ /bot mt5_desk health to check status
```

**API timeout:**
```
⚠ Command timed out: /brief
Reason: Crew run exceeded 25-minute limit.
→ /status to get last cached brief
```

---

## Summary of Required Changes to `telegram_bridge.py`

To achieve CEO-standard output, the following formatting changes are needed:

| Change | Scope | Effort |
|--------|-------|--------|
| Replace `[RED]`/`[AMBER]`/`[GREEN]` with 🔴/🟡/🟢 | All `_summarize_*` methods | Low |
| Add exec summary line (count by status) | `_summarize_holding_brief`, `_summarize_divisions_brief` | Low |
| Add target+variance to every metric | Same methods | Low |
| Add owner + deadline to action items | Same methods | Medium |
| Replace raw JSON bot output | `_summarize_tool_result` → `run_trading_script` branch | Low |
| Rewrite `/status` (`daily_brief`) response | `_summarize_tool_result` → `daily_brief` branch | Low |
| Add section dividers (─ lines) | All methods | Low |
| Trim CTA to single command | All methods | Low |
| Rewrite `/help` with grouped sections | `_format_help` | Low |
| Format error responses consistently | `_summarize_tool_result` error branch | Low |

All changes are formatting-only — no logic, no schema changes.
