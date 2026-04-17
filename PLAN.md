# AI Holding Company — Master Plan
**Version:** 5  
**Owner:** J (CEO)  
**Last updated:** 2026-04-13  
**Supersedes:** All previous plan versions (v1–v4).

---

> **FOR ANY AI TOOL OR AGENT READING THIS FILE:**  
> This is the canonical reference for all work on the AI Holding Company system.  
> Read this file completely before touching any code, config, prompt, or data.  
> Every rule here is non-negotiable unless a rule-change is explicitly recorded in section 10.  
> If in doubt: stop, escalate to the Managing Agent, and wait.

---

## 1. What This System Is

**AI Holding Company** is a fully local AI-powered business-management layer that sits on top of existing operations without modifying their core logic. It manages:

- Two trading bots (Forex/MT5, Polymarket) — one desktop, one VPS
- Two websites (Trading Tools, Productivity Tools / FreeTraderHub)
- A growing set of divisions covering trading, web, research, commercial, content, and marketing

**Strategic intent:** Evolve from an AI operations/reporting layer into an AI business-management layer. The system not only monitors and reports — it assesses feasibility, scores initiatives, estimates ROI, and surfaces the right decisions at the right time, while the CEO retains full decision authority.

The CEO (J) decides. Divisions plan and execute. The Managing Agent coordinates, QAs, and filters. The system saves CEO time while raising decision quality.

---

## 2. Non-Negotiable Rules

These rules cannot be overridden by any agent, plan, or tool.

| # | Rule | Detail |
|---|------|--------|
| R1 | **100% local** | All inference via Ollama only. No cloud APIs. No OpenAI, Anthropic Claude API, Grok, Gemini, or equivalent. |
| R2 | **Bots stay untouched** | MT5 and Polymarket bot source is read-only. No writes, no deploys, no parameter changes without explicit CEO approval via the Loop. |
| R3 | **Website source is protected** | Website source is read-only for all agents except the Developer Tool, and only after CEO approval via the Loop. |
| R4 | **No auto-publish of AI prose** | Deterministic data may auto-publish after plan approval. AI-generated prose requires CEO review before any publish. All external content and website changes escalate under R4 and R3 combined. |
| R5 | **No live money actions without CEO** | Fund movement, trade execution, cost commitment >$50, drawdown response — all require CEO approval. |
| R6 | **Compliance Guardian always runs** | Vets every approved plan against R1–R11 before Stage 04 fires. Cannot be disabled. |
| R7 | **MA copied on all comms** | If CEO communicates directly with a divisional head, the Managing Agent is always copied. |
| R8 | **Developer Tool scope gate** | qwen2.5-coder:7b writes only to files inside `ai-holding-company/`. Never to bot source, website source, or any file outside this folder. |
| R9 | **Two net-negative weeks = halt** | If Time Saved sheet shows net-negative CEO hours for two consecutive weeks, all new work halts. Review the operating model before adding anything. |
| R10 | **Silence by default** | No unsolicited messages unless: (a) decision pending for CEO, (b) status colour changed, or (c) seven days passed with no communication. |
| R11 | **No OpenClaw — python-telegram-bot only** | OpenClaw is prohibited. The Telegram gateway must use the `python-telegram-bot` library (direct Bot API polling, pure Python, no Docker, no intermediate broker). The bot token is stored in the local `.env` file only and never transmitted to a third-party service. Compliance Guardian blocks any plan that introduces OpenClaw, a message broker, or any Docker-based Telegram gateway. |

---

## 3. Organisation Structure

### Near-term org (next 8 weeks)
```
┌──────────────────────────────────────────┐
│              CEO  (J)                    │
│         AI Holding Company               │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│          MANAGING AGENT (MA)             │
│      COO · coordinates · QA · escalates  │
│          model: llama3.1:8b              │
└──┬──────┬──────┬──────────┬─────────────┘
   │      │      │          │        │
TRADING  WEB  RESEARCH  COMMERCIAL  CONTENT
                           (was       STUDIO
                          Treasury)  (light)
```

### Target org (post-stability)
```
Trading · Websites/Product · Research · Commercial · Content Studio · Marketing · Ideas (optional)
```

### Division status
| Division | Status | Notes |
|----------|--------|-------|
| Trading | LIVE (AMBER) | Polymarket recency stale — Stage D fixes |
| Websites | LIVE (RED) | Research brief freshness — Stage D fixes |
| Research | PLANNED (Stage E) | On-demand first, weekly opt-in |
| Commercial | PLANNED (Stage G) | Replaces Treasury. Full business-management mandate. |
| Content Studio | PLANNED (Stage J) | Add after Stage D green. Light first — inside Websites or standalone. |
| Marketing | PLANNED (Stage K) | Only after A, B, D stable and green. 1 campaign decision/week max. |
| Ideas | OPTIONAL | Reconsider once Commercial + Marketing exist. |

---

## 4. The Operating Model — Six-Stage Loop

Every piece of work runs through this loop. No exceptions.

```
01 GOAL  →  02 PLAN  →  03 APPROVE  →  04 EXECUTE  →  05 REPORT  →  06 JUDGE
  CEO          Division    MA or CEO      Division       Div → MA       CEO
  issues       proposes    + Guardian     runs           QA gate        accepts or
  in chat      how         (see §5)       the work       then CEO       re-tasks
```

**Commercial scoring gate (new in v5):** Before any new initiative reaches the Board Pack or Stage 03, Commercial must score it with: expected upside, effort/cost, confidence level, and a go/no-go recommendation. No unscored initiative enters execution.

**Three standing rules:**
1. Decision Queue hard-capped at 5 open items. A sixth waits.
2. System is silent by default (R10).
3. Two consecutive net-negative weeks halts all new division rollout (R9).

---

## 5. Managing Agent — Role, Authority & Escalation Rules

### Always escalates to CEO (fixed rules)
1. Anything touching live money or cost commitment >$50 (R5)
2. Code deployment of any kind (R8)
3. External publishing — anything going live on public-facing sites (R4)
4. New plan type not seen before
5. Compliance Guardian has flagged the plan (R6)
6. Goal running >2× its estimated effort
7. Inter-division conflict MA cannot resolve in one cycle
8. MA genuinely uncertain — cannot classify against ruleset
9. **Any new initiative without all 5 KPI fields** (owner, upside, effort/cost, KPI/metric, review date) — see §8

### MA handles without CEO
- Routine monitoring and data-pull approvals
- Intra-division operational decisions
- Progress chasing within approved scope
- QA verification of completed work against success criteria
- Scheduling and task ordering inside approved scope
- Copying CEO on direct CEO-to-division comms

### Escalation message format (when uncertain)
```
[ESCALATION] Cannot classify: <one-line explanation>.
Options: <A>, <B>.
Recommendation: <X>.
```
CEO replies. MA logs and acts. MA never guesses.

---

## 6. Guardrails (v5 — prevent complexity creep)

These guardrails apply to all new division rollouts and initiatives.

| # | Guardrail | Rule |
|---|-----------|------|
| G1 | **Sequence guard** | Do not add new outward-facing divisions until Stage A, B, and D are stable and green. |
| G2 | **Load guard** | Do not activate more than one new division at a time. Each division must prove value against explicit success criteria before another is activated. |
| G3 | **Decision guard** | Marketing: max 1 campaign decision/week. Content: operates from approved briefs or approved campaign plans only — no open-ended work. Commercial: must score any new initiative before it reaches the Board Pack. |
| G4 | **Publishing guard** | Content may draft assets. All public publishing, website changes, or external content releases escalate under R3 and R4. No exceptions. |
| G5 | **KPI guard** | No new initiative enters execution without: named owner, expected upside, expected effort/cost, KPI or success metric, review date, post-launch measurement plan. |
| G6 | **Silence guard** | New divisions obey R10 (silence by default). They surface only: pending decisions, colour/status changes, scheduled digest outputs explicitly allowed by policy. |
| G7 | **Complexity stop-rule** | If two consecutive weeks show net-negative time saved (R9), pause all new division rollout and review the operating model before adding anything. |

---

## 7. Model Architecture

All inference local via Ollama. Zero cloud APIs.

| Model | Tag | Role | Notes |
|-------|-----|------|-------|
| Llama 3.1 8B | `llama3.1:8b` | MA / CEO Layer / Division Managers | Primary reasoning. Phase 2, 3, MA coordination, Commercial analysis, Board Pack synthesis. |
| Llama 3.2 3B | `llama3.2:latest` | Telegram Router / NLU Intake | Fast intent parser. Translates plain-English CEO messages into structured Goals. |
| Qwen2.5 Coder 7B | `qwen2.5-coder:7b` | Developer Tool (Stage I) | `ai-holding-company/` scope only. CEO reviews diff before deploy. |
| nomic-embed-text | `nomic-embed-text:latest` | Semantic Memory (Stage I+) | Embedding only. Not generative. Future semantic search. |

---

## 8. Board Pack Requirements (v5 upgrade)

Every proposed decision in the weekly Board Pack must include all eight fields. MA blocks any decision missing a field from reaching the CEO.

| Field | Required content |
|-------|-----------------|
| **Rationale** | Why this decision / initiative is being proposed now |
| **Expected upside** | Quantified where possible (revenue, time saved, risk reduced) |
| **Expected effort / cost** | Time, compute, money — realistic estimate |
| **Confidence level** | High / Medium / Low with one-line reason |
| **Owner** | Named division or agent responsible for execution |
| **Deadline / review date** | Hard date for completion or first review |
| **Dissent / counter-argument** | Dissent agent must file one objection minimum |
| **Post-launch measurement plan** | How success will be measured after execution |

**Commercial must score any new initiative** (upside, effort, confidence, go/no-go) before it reaches the Board Pack. Unscored initiatives are blocked by MA.

---

## 9. Commercial Division Charter (replaces Treasury)

Commercial owns the business-management function. Finance Reporting and Risk Monitoring are sub-functions inside Commercial, not the whole division.

**Commercial answers:**
- Should we do this? (feasibility)
- What is the expected payoff? (ROI projection)
- What does success look like numerically? (KPI definition)
- Was it worth it afterward? (post-launch review vs forecast)

**Sub-functions:**
1. **Finance Reporting** — daily PNL roll-up, weekly P&L statement
2. **Business Case / Feasibility** — go/no-go assessment for new initiatives
3. **ROI & Impact** — projection, scoring, prioritisation, scenario modelling
4. **Risk Monitoring** — drawdown alerts, cost spike detection, exposure flags

**Commercial model:** llama3.1:8b for analysis; Python tools for all arithmetic (no LLM arithmetic).

---

## 10. Capability Decisions

Locked. Do not re-open without a CEO directive.

| Capability | Status | Condition |
|-----------|--------|-----------|
| Monitoring, start/stop, coordination | ✅ IN | Autonomous; parameter changes need CEO approval |
| Real-time reporting and alerts | ✅ IN | Silence by default; daily digest opt-in |
| Plain-English goal submission (NLU) | ✅ IN | llama3.2:3b router; slash commands for approvals |
| Human-in-the-loop (MA + CEO gates) | ✅ IN | See §4, §5 |
| Non-disruptive integration | ✅ IN | Existing bots untouched; thin wrappers only |
| Auto-publish deterministic data | ✅ IN (gated) | After plan approval; no AI prose auto-publish |
| Commercial Division (full mandate) | ✅ IN | Replaces Treasury. Feasibility, ROI, risk, finance. |
| Content Studio | ✅ IN (staged) | After Stage D green. Light, brief-driven only. |
| Marketing Division | ✅ IN (gated) | Only after A, B, D green. 1 campaign/week max. |
| Developer Tool (internal scripts only) | ✅ IN (Stage I) | `ai-holding-company/` scope; CEO reviews diff |
| Developer Agent for bot/website source | ⏸ DEFER | Re-evaluate after Stage I |
| Full code autonomy | ❌ OUT | Quality insufficient for production logic |
| Grok / Claude API / any cloud LLM | ❌ OUT (hard) | Violates R1. Non-negotiable. |
| OpenClaw / Docker Telegram gateway | ❌ OUT (hard) | Violates R11. Use python-telegram-bot only. |
| Ideas Division | ⚪ OPTIONAL | Reconsider once Commercial + Marketing exist. 1/week cap + Critic. |

---

## 11. Stage Plan — Current Status

| Stage | Title | Status | Priority | Guardrails |
|-------|-------|--------|----------|------------|
| A | Telegram Gateway (python-telegram-bot) + NLU + MA + Compliance Guardian + Silence | ✅ COMPLETE | P0 | R11 |
| B | Scheduler Verification & Self-Heal | ✅ COMPLETE | P0 | — |
| C | Sanitizer & Allowlist Remediation | ✅ COMPLETE | P1 (parallel) | — |
| D | Operational Signals → GREEN | 🔴 NOT STARTED | P1 | Unblock G1 |
| G | Commercial Division | 🔴 NOT STARTED | P1 | G2: one at a time |
| E | Research Division (on-demand first) | 🔴 NOT STARTED | P2 | G2 |
| H | Holding Board v2 + Board Pack upgrade | ✅ COMPLETE | P2 | — |
| J | Content Studio (light) | 🔴 NOT STARTED | P2 | G1, G2, G3, G4 |
| I | Steady State + Developer Tool + Time-Saved Proof | 🔴 NOT STARTED | P3 | — |
| K | Marketing Division | 🔴 NOT STARTED | P3 | G1 (A+B+D must be green), G2, G3 |
| F | Ideas Division | ⚪ OPTIONAL | P3 | Reconsider once G+K exist |

**Critical path:** A → B → D → G → H → J → I  
**Parallel:** C alongside A/B  
**Gated:** K only after A, B, D green  
**Optional:** F

**Infrastructure already live:**
- Phase 1 (Telemetry / Daily Brief): ✅ LIVE — `daily_brief_latest.json` generating
- Phase 2 (Division Crews): ✅ LIVE — `crewai_hierarchical`, trading=AMBER, websites=RED
- Phase 3 (CEO / Holding Board): ✅ LIVE — `crewai_ceo`, `company_status=RED`
- Stage A (Telegram Gateway + NLU + MA + Compliance Guardian + Silence): ✅ LIVE — confirmed working 2026-04-14
- Stage B (Scheduler Verification & Self-Heal): ✅ LIVE — confirmed working 2026-04-14. Scheduler config: Windows Task Scheduler (BridgeStartup + MorningBrief), jobs via tool_router.py. Self-heal wired. /scheduler command live.
- Stage C (Sanitizer & Allowlist Remediation): ✅ LIVE — commit 261098d. safe_chat() wraps all Ollama calls. R8 path guard, R1 network guard, R11 provider scrub all active. /violations command live. 19 tests passing.
- Stage H (Holding Board v2 + Board Pack): ✅ LIVE — 8-field Board Pack, dissent agent, MA gate, board_pack mode, 18 tests passing. /board pack Telegram command live.
- Latest commit: `67ec6c1`

---

## 12. File Structure

```
ai-holding-company/
├── PLAN.md                          ← THIS FILE — read first, always
├── SOUL.md                          ← company identity and personality
├── HEARTBEAT.md                     ← scheduled task instructions
├── heartbeat.yaml                   ← scheduler config
├── telegram_bot.py                  ← Telegram gateway (python-telegram-bot, no Docker)
├── config/
│   ├── .env.example                 ← environment template (copy to .env, add BOT_TOKEN)
│   └── .env                         ← local only — never commit — contains BOT_TOKEN
├── tools/
│   ├── read_bot_logs.py
│   ├── check_website.py
│   └── system_status.py
├── artifacts/                       ← generated outputs
│   ├── daily_brief_latest.json
│   ├── phase2_divisions_latest.json
│   ├── phase3_holding_latest.json
│   └── ...
└── docs/
    ├── AI-Holding-Company_Operating-Model.png
    ├── AI-Holding-Company_Goals-Decisions-Tracker.xlsx
    └── AI-Holding-Company_Sharpened-Project-Plan-v5.docx
```

**Security note (R11):** No `docker-compose.yml` for Telegram. No OpenClaw. The gateway is `telegram_bot.py` — a single Python file using `python-telegram-bot`. It polls the Telegram API directly (outbound HTTPS only). The `BOT_TOKEN` is stored in `.env` (git-ignored). No third-party message broker ever touches the token.

---

## 13. Out of Scope

Any agent proposing work in these areas must be blocked by the Compliance Guardian.

- Auto-trading or auto-fund-movement (Treasury/Commercial is read-only; possible Phase 5)
- Code writes to MT5, Polymarket, or website source without CEO approval via Loop
- Any cloud LLM: Claude API, OpenAI, Grok, Gemini, or equivalent
- OpenClaw, or any Docker-based or broker-based Telegram gateway (violates R11)
- Multi-CEO or multi-tenant access
- Cross-machine deployment (single Windows desktop is the target)
- Web UI beyond the local observability dashboard
- Content Studio publishing without CEO approval under R3/R4
- Marketing campaigns without Commercial scoring first
- Ideas at >1/week or without Critic counter-argument

---

## 14. How to Use This Document

**If you are an AI tool or agent:**
1. Read this file completely before doing anything.
2. Check your proposed action against R1–R11 (§2) and guardrails G1–G7 (§6).
3. If your action requires CEO approval (§5), stop and surface it via the Managing Agent.
4. Commercial must score any new initiative before it reaches the Board Pack (§8).
5. If uncertain, escalate. Do not guess.
6. Reference this file's section numbers in plans and reports (e.g., "per PLAN.md §6/G1, this is blocked until Stage D is green").

**If you are the CEO (J):**
1. Start every session by checking Decisions Pending in the Tracker or sending `/pending` in Telegram.
2. Issue new work by typing your goal in plain English.
3. Check §11 (stage status) when starting a new build phase.
4. This file is updated at the end of every completed stage alongside the v5 docx.

---

*End of PLAN.md — version 5.2 — AI Holding Company — 2026-04-17*  
*v5.1 change: Added R11 (No OpenClaw; python-telegram-bot only). Updated Stage A, file structure, Out of Scope, and Capability Decisions.*  
*v5.2 change: Stage H complete. Holding Board v2 live. 8-field Board Pack, dissent_agent, MA gate, board_pack mode in tool_router, /board pack Telegram command, 18 Stage H tests.*
