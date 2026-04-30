# AI Holding Company â€” Master Plan
**Version:** 5.7  
**Owner:** J (CEO)  
**Last updated:** 2026-04-18  
**Supersedes:** All previous plan versions (v1â€“v4).  
**v5.2 change:** Stage D updated â€” portfolio analysis complete, Integration Readiness Sprint defined. Stage D execution tasks documented in Â§11.1. Property charters written for all four portfolio properties.  
**v5.3 change:** Stage D closed. Trading=GREEN, Websites=GREEN. 23/23 tests passing, commit e533073. G1 unblocked. Stage G (Commercial Division) now active â€” prompts in STAGE_G_PROMPTS.md.  
**v5.4 change:** Stage G closed. Commercial Division live, 45/45 tests passing, commit 1367323. Codex review: 8 issues found and resolved (including HIGH â€” inverted risk thresholds). Stage H (Holding Board v2) now active â€” prompts in STAGE_H_PROMPTS.md.
**v5.5 change:** Stage J closed. Content Studio (light) is now live as brief-driven only with CEO approval gating (R3/R4). Added `crews/content_studio.yaml`, `scripts/content_studio.py`, phase2 integration, Telegram `/content` + `/content_status`, and 14 passing Content Studio tests. Two consecutive phase2 runs confirmed `content_studio=GREEN`.
**v5.6 change:** Stage I closed. Added Developer Tool (`/develop`, `/develop_approve`, `/develop_deny`, `/develop_status`) with R8 scope gate and CEO approval workflow, semantic memory initialization (`nomic-embed-text`), and time-saved tracking with R9 guardrail proof at 6.25 hours/week.
**v5.7 change:** Stage L opened - FreeTraderHub Prop-Firm Pivot (Prop Cockpit) approved. G8 Wedge Guard adopted (§6). R12 Net-Negative Value Halt adopted (§2). R12 Applicability Matrix added (per-property-type formulas: website, trading_bot, internal_tool, b2b_service). Websites Division Charter expanded to include product + revenue + pipeline KPIs. Board Pack v2 Property P&L Block activated (§8.1). FreeTraderHub charter v1 active with all six required R12 fields.
**v5.8 change:** Efficiency LLM exception adopted. Core runtime operations remain Ollama-local, while DeepSeek and `scripts/free_llm_client.py` may be used as opt-in efficiency tooling for development, analysis, summarisation, and research support when explicitly configured. External LLMs are still barred from live trading, board decisions, scoring truth, owner chat autonomy, memory truth, and unattended execution.

---

> **FOR ANY AI TOOL OR AGENT READING THIS FILE:**  
> This is the canonical reference for all work on the AI Holding Company system.  
> Read this file completely before touching any code, config, prompt, or data.  
> Every rule here is non-negotiable unless a rule-change is explicitly recorded in section 10.  
> If in doubt: stop, escalate to the Managing Agent, and wait.

---

## 1. What This System Is

**AI Holding Company** is a fully local AI-powered business-management layer that sits on top of existing operations without modifying their core logic. It manages:

- Two trading bots (Forex/MT5, Polymarket) â€” one desktop, one VPS
- Two websites (Trading Tools, Productivity Tools / FreeTraderHub)
- A growing set of divisions covering trading, web, research, commercial, content, and marketing

**Strategic intent:** Evolve from an AI operations/reporting layer into an AI business-management layer. The system not only monitors and reports â€” it assesses feasibility, scores initiatives, estimates ROI, and surfaces the right decisions at the right time, while the CEO retains full decision authority.

The CEO (J) decides. Divisions plan and execute. The Managing Agent coordinates, QAs, and filters. The system saves CEO time while raising decision quality.

---

## 2. Non-Negotiable Rules

These rules cannot be overridden by any agent, plan, or tool.

| # | Rule | Detail |
|---|------|--------|
| R1 | **Runtime local; efficiency LLM exception** | Operational inference stays Ollama-local for briefs, scoring, board decisions, memory truth, owner chat, and live-money workflows. DeepSeek and `scripts/free_llm_client.py` are allowed only as opt-in efficiency tooling for development, review, research support, and summarisation when explicitly configured by environment variables. No external LLM may make unattended operational decisions, execute trades, move money, publish AI prose, alter source outside approved gates, or become canonical truth. |
| R2 | **Bots stay untouched** | MT5 and Polymarket bot source is read-only. No writes, no deploys, no parameter changes without explicit CEO approval via the Loop. |
| R3 | **Website source is protected** | Website source is read-only for all agents except the Developer Tool, and only after CEO approval via the Loop. |
| R4 | **No auto-publish of AI prose** | Deterministic data may auto-publish after plan approval. AI-generated prose requires CEO review before any publish. All external content and website changes escalate under R4 and R3 combined. |
| R5 | **No live money actions without CEO** | Fund movement, trade execution, cost commitment >$50, drawdown response â€” all require CEO approval. |
| R6 | **Compliance Guardian always runs** | Vets every approved plan against R1â€“R11 before Stage 04 fires. Cannot be disabled. |
| R7 | **MA copied on all comms** | If CEO communicates directly with a divisional head, the Managing Agent is always copied. |
| R8 | **Developer Tool scope gate** | qwen2.5-coder:7b writes only to files inside `ai-holding-company/`. Never to bot source, website source, or any file outside this folder. |
| R9 | **Two net-negative weeks = halt** | If Time Saved sheet shows net-negative CEO hours for two consecutive weeks, all new work halts. Review the operating model before adding anything. |
| R10 | **Silence by default** | No unsolicited messages unless: (a) decision pending for CEO, (b) status colour changed, or (c) seven days passed with no communication. |
| R11 | **No OpenClaw â€” python-telegram-bot only** | OpenClaw is prohibited. The Telegram gateway must use the `python-telegram-bot` library (direct Bot API polling, pure Python, no Docker, no intermediate broker). The bot token is stored in the local `.env` file only and never transmitted to a third-party service. Compliance Guardian blocks any plan that introduces OpenClaw, a message broker, or any Docker-based Telegram gateway. |
| R12 | **Net-negative value halt (per property)** | If a portfolio property's Commercial-tracked value delta (revenue + quantified value - time invested x internal_rate - direct costs) is net-negative for 4 consecutive weeks while in an R12-eligible phase, all new investment in that property halts. CEO + Commercial conduct a wedge and operating-model review before work resumes. Formula varies by property_type (see Applicability Matrix in `RULE_CHANGE_PROPOSAL_R12_NET_NEGATIVE_VALUE_HALT.md`). Mirrors R9 at the property level. |

---

## 3. Organisation Structure

### Near-term org (next 8 weeks)
```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚              CEO  (J)                    â”‚
â”‚         AI Holding Company               â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
               â”‚
               â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚          MANAGING AGENT (MA)             â”‚
â”‚      COO Â· coordinates Â· QA Â· escalates  â”‚
â”‚          model: llama3.1:8b              â”‚
â””â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
   â”‚      â”‚      â”‚          â”‚        â”‚
TRADING  WEB  RESEARCH  COMMERCIAL  CONTENT
                           (was       STUDIO
                          Treasury)  (light)
```

### Target org (post-stability)
```
Trading Â· Websites/Product Â· Research Â· Commercial Â· Content Studio Â· Marketing Â· Ideas (optional)
```

### Division status
| Division | Status | Notes |
|----------|--------|-------|
| Trading | LIVE (GREEN) | MT5 + Polymarket. Monitoring stable. |
| Websites | LIVE (GREEN) | FreeTraderHub. Uptime stable. Charter v2 (2026-04-18): mandate expanded from uptime+Lighthouse to include product KPIs (sessions, WAFT, tool completion, returning rate), revenue KPIs (via Commercial), and pipeline health (Content drafts, pages indexed, backlinks acquired). Primary owner of Stage L. |
| Research | PLANNED (Stage E) | On-demand first, weekly opt-in â€” wait for Stage H |
| Commercial | LIVE (GREEN) | Finance reporting, risk check, initiative scoring â€” commit 1367323 |
| Content Studio | LIVE (GREEN) | Brief-driven only. CEO approval gate enforced (R3/R4). Stage J complete 2026-04-17. |
| Marketing | PLANNED (Stage K) | Only after A, B, D stable and green. 1 campaign decision/week max. |
| Ideas | OPTIONAL | Reconsider once Commercial + Marketing exist. |

---

## 4. The Operating Model â€” Six-Stage Loop

Every piece of work runs through this loop. No exceptions.

```
01 GOAL  â†’  02 PLAN  â†’  03 APPROVE  â†’  04 EXECUTE  â†’  05 REPORT  â†’  06 JUDGE
  CEO          Division    MA or CEO      Division       Div â†’ MA       CEO
  issues       proposes    + Guardian     runs           QA gate        accepts or
  in chat      how         (see Â§5)       the work       then CEO       re-tasks
```

**Commercial scoring gate (new in v5):** Before any new initiative reaches the Board Pack or Stage 03, Commercial must score it with: expected upside, effort/cost, confidence level, and a go/no-go recommendation. No unscored initiative enters execution.

**Three standing rules:**
1. Decision Queue hard-capped at 5 open items. A sixth waits.
2. System is silent by default (R10).
3. Two consecutive net-negative weeks halts all new division rollout (R9).

---

## 5. Managing Agent â€” Role, Authority & Escalation Rules

### Always escalates to CEO (fixed rules)
1. Anything touching live money or cost commitment >$50 (R5)
2. Code deployment of any kind (R8)
3. External publishing â€” anything going live on public-facing sites (R4)
4. New plan type not seen before
5. Compliance Guardian has flagged the plan (R6)
6. Goal running >2Ã— its estimated effort
7. Inter-division conflict MA cannot resolve in one cycle
8. MA genuinely uncertain â€” cannot classify against ruleset
9. **Any new initiative without all 5 KPI fields** (owner, upside, effort/cost, KPI/metric, review date) â€” see Â§8

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

## 6. Guardrails (v5 â€” prevent complexity creep)

These guardrails apply to all new division rollouts and initiatives.

| # | Guardrail | Rule |
|---|-----------|------|
| G1 | **Sequence guard** | Do not add new outward-facing divisions until Stage A, B, and D are stable and green. |
| G2 | **Load guard** | Do not activate more than one new division at a time. Each division must prove value against explicit success criteria before another is activated. |
| G3 | **Decision guard** | Marketing: max 1 campaign decision/week. Content: operates from approved briefs or approved campaign plans only â€” no open-ended work. Commercial: must score any new initiative before it reaches the Board Pack. |
| G4 | **Publishing guard** | Content may draft assets. All public publishing, website changes, or external content releases escalate under R3 and R4. No exceptions. |
| G5 | **KPI guard** | No new initiative enters execution without: named owner, expected upside, expected effort/cost, KPI or success metric, review date, post-launch measurement plan. |
| G6 | **Silence guard** | New divisions obey R10 (silence by default). They surface only: pending decisions, colour/status changes, scheduled digest outputs explicitly allowed by policy. |
| G7 | **Complexity stop-rule** | If two consecutive weeks show net-negative time saved (R9), pause all new division rollout and review the operating model before adding anything. |
| G8 | **Wedge guard** | No initiative on a portfolio property may be scored, approved, or executed unless it demonstrably serves that property's defined wedge. Each property's wedge is recorded in its charter and may be changed only through the Â§10 rule-change process. Compliance Guardian blocks initiatives that fail this test before they reach the Board Pack. Applied per-property; never cross-applied. |

---

## 7. Model Architecture

Operational inference is local via Ollama. External LLMs are allowed only under the R1 efficiency exception.

| Model | Tag | Role | Notes |
|-------|-----|------|-------|
| Llama 3.1 8B | `llama3.1:8b` | MA / CEO Layer / Division Managers | Primary reasoning. Phase 2, 3, MA coordination, Commercial analysis, Board Pack synthesis. |
| Llama 3.2 3B | `llama3.2:latest` | Telegram Router / NLU Intake | Fast intent parser. Translates plain-English CEO messages into structured Goals. |
| Qwen2.5 Coder 7B | `qwen2.5-coder:7b` | Developer Tool (Stage I) | `ai-holding-company/` scope only. CEO reviews diff before deploy. |
| nomic-embed-text | `nomic-embed-text:latest` | Semantic Memory (Stage I+) | Embedding only. Not generative. Future semantic search. |
| DeepSeek V3 | `deepseek-chat` | Dev pipeline builder/reviewer | External API exception. Requires `DEEPSEEK_API_KEY`. Never used for live operations, board truth, memory truth, or money actions. |
| Free-provider router | `scripts/free_llm_client.py` | Optional efficiency experiments | External API exception. Provider keys are opt-in only. Output is advisory and must not bypass approval gates. |

---

## 8. Board Pack Requirements (v5 upgrade)

Every proposed decision in the weekly Board Pack must include all eight fields. MA blocks any decision missing a field from reaching the CEO.

| Field | Required content |
|-------|-----------------|
| **Rationale** | Why this decision / initiative is being proposed now |
| **Expected upside** | Quantified where possible (revenue, time saved, risk reduced) |
| **Expected effort / cost** | Time, compute, money â€” realistic estimate |
| **Confidence level** | High / Medium / Low with one-line reason |
| **Owner** | Named division or agent responsible for execution |
| **Deadline / review date** | Hard date for completion or first review |
| **Dissent / counter-argument** | Dissent agent must file one objection minimum |
| **Post-launch measurement plan** | How success will be measured after execution |

**Commercial must score any new initiative** (upside, effort, confidence, go/no-go) before it reaches the Board Pack. Unscored initiatives are blocked by MA.

### 8.1  Property P&L Block (v2, added 2026-04-18)

Every active property renders a **Property P&L Block** at the top of the
weekly Board Pack. Six stacked sections: Audience, Revenue, Pipeline,
Top Movers, Status, plus R12 counter. Reads in 30 seconds. Uses the
formula dictated by R12 Applicability Matrix for the property's
declared `property_type`.

Full specification and ASCII template:
`STAGE_L_BOARD_PACK_V2_PROPERTY_PNL_TEMPLATE.md`

Activation schedule:
- **FreeTraderHub:** 2026-04-21 (Monday after Stage L approval)
- **Free Utility Tools:** on wedge declaration + charter completion
- **MT5 Forex Bot:** on charter completion - formula `trading_bot_v1` (trading P&L excluded from R12)
- **Polymarket Bot:** on charter completion - formula `trading_bot_v1`

MA renders one block per active property, ordered by strategic priority.
If data source is unavailable for a field, render `-` and log in cover note.

---

## 9. Commercial Division Charter (replaces Treasury)

Commercial owns the business-management function. Finance Reporting and Risk Monitoring are sub-functions inside Commercial, not the whole division.

**Commercial answers:**
- Should we do this? (feasibility)
- What is the expected payoff? (ROI projection)
- What does success look like numerically? (KPI definition)
- Was it worth it afterward? (post-launch review vs forecast)

**Sub-functions:**
1. **Finance Reporting** â€” daily PNL roll-up, weekly P&L statement
2. **Business Case / Feasibility** â€” go/no-go assessment for new initiatives
3. **ROI & Impact** â€” projection, scoring, prioritisation, scenario modelling
4. **Risk Monitoring** â€” drawdown alerts, cost spike detection, exposure flags

**Commercial model:** llama3.1:8b for analysis; Python tools for all arithmetic (no LLM arithmetic).

---

## 10. Capability Decisions

Locked. Do not re-open without a CEO directive.

| Capability | Status | Condition |
|-----------|--------|-----------|
| Monitoring, start/stop, coordination | âœ… IN | Autonomous; parameter changes need CEO approval |
| Real-time reporting and alerts | âœ… IN | Silence by default; daily digest opt-in |
| Plain-English goal submission (NLU) | âœ… IN | llama3.2:3b router; slash commands for approvals |
| Human-in-the-loop (MA + CEO gates) | âœ… IN | See Â§4, Â§5 |
| Non-disruptive integration | âœ… IN | Existing bots untouched; thin wrappers only |
| Auto-publish deterministic data | âœ… IN (gated) | After plan approval; no AI prose auto-publish |
| Commercial Division (full mandate) | âœ… IN | Replaces Treasury. Feasibility, ROI, risk, finance. |
| Content Studio | âœ… IN (staged) | After Stage D green. Light, brief-driven only. |
| Marketing Division | âœ… IN (gated) | Only after A, B, D green. 1 campaign/week max. |
| Developer Tool (internal scripts only) | âœ… IN (Stage I) | `ai-holding-company/` scope; CEO reviews diff |
| Developer Agent for bot/website source | â¸ DEFER | Re-evaluate after Stage I |
| Full code autonomy | âŒ OUT | Quality insufficient for production logic |
| External LLMs for runtime control | âŒ OUT (hard) | Violates R1. No external model may control live operations, trading, board truth, memory truth, owner chat autonomy, or publishing. |
| External LLMs for efficiency tooling | âœ… IN (restricted) | DeepSeek and `scripts/free_llm_client.py` are allowed only as opt-in advisory tools for development/review/research/summarisation; CEO gates still apply. |
| OpenClaw / Docker Telegram gateway | âŒ OUT (hard) | Violates R11. Use python-telegram-bot only. |
| Ideas Division | âšª OPTIONAL | Reconsider once Commercial + Marketing exist. 1/week cap + Critic. |

---

## 11. Stage Plan â€” Current Status

| Stage | Title | Status | Priority | Guardrails |
|-------|-------|--------|----------|------------|
| A | Telegram Gateway (python-telegram-bot) + NLU + MA + Compliance Guardian + Silence | âœ… COMPLETE | P0 | R11 |
| B | Scheduler Verification & Self-Heal | âœ… COMPLETE | P0 | â€” |
| C | Sanitizer & Allowlist Remediation | âœ… COMPLETE | P1 (parallel) | â€” |
| D | Operational Signals â†’ GREEN | âœ… COMPLETE â€” 2026-04-15. Trading=GREEN, Websites=GREEN. commit e533073 | P1 | Unblock G1 |
| G | Commercial Division | âœ… COMPLETE â€” 2026-04-15. commit 1367323. 45/45 tests. Codex CLEAN. | P1 | G2: one at a time |
| E | Research Division (on-demand first) | ðŸ”´ NOT STARTED | P2 | G2 â€” wait for H |
| H | Holding Board v2 + Board Pack upgrade | ðŸŸ¡ IN PROGRESS â€” see Â§11.3 | P2 | â€” |
| J | Content Studio (light) | âœ… COMPLETE â€” 2026-04-17. Brief-driven only, CEO gate enforced, 14 tests passing, commit 9e7323d. | P2 | G1, G2, G3, G4 |
| I | Steady State + Developer Tool + Time-Saved Proof | âœ… COMPLETE â€” 2026-04-17. Developer Tool (/develop, R8/R5 gates), semantic memory (nomic-embed-text), R9 GREEN (6.25 h/week), 35 tests, commit 4b9fc36. | P3 | â€” |
| K | Marketing Division | âœ… COMPLETE — 2026-04-17. G3 guardrail (max 1 campaign/week), Commercial scoring integration, R3/R4 CEO approval gates, 10 tests passing, commit 272eab2. | P3 | G1 (A+B+D must be green), G2, G3 |
| L | Stage L â€” FreeTraderHub Prop-Firm Pivot (Prop Cockpit) | ðŸŸ¡ IN PROGRESS â€” 2026-04-18. G8 + R12 adopted. 90-day sprint. Value readiness Day 60 (2026-06-17). | P2 | G1, G2, G3, G4, G5, G8 |
| F | Ideas Division | âšª OPTIONAL | P3 | Reconsider once G+K exist |

**Critical path:** A â†’ B â†’ D â†’ G â†’ H â†’ J â†’ I â†’ L  
**Parallel:** C alongside A/B  
**Gated:** K only after A, B, D green  
**Optional:** F

**Infrastructure already live:**
- Phase 1 (Telemetry / Daily Brief): âœ… LIVE â€” `daily_brief_latest.json` generating
- Phase 2 (Division Crews): âœ… LIVE â€” `crewai_hierarchical`, trading=GREEN, websites=GREEN, content_studio=GREEN
- Phase 3 (CEO / Holding Board): âœ… LIVE â€” `crewai_ceo`, `company_status=GREEN`
- Stage A (Telegram Gateway + NLU + MA + Compliance Guardian + Silence): âœ… LIVE â€” confirmed working 2026-04-14
- Stage B (Scheduler Verification & Self-Heal): âœ… LIVE â€” confirmed working 2026-04-14. Scheduler config: Windows Task Scheduler (BridgeStartup + MorningBrief), jobs via tool_router.py. Self-heal wired. /scheduler command live.
- Stage C (Sanitizer & Allowlist Remediation): âœ… LIVE â€” commit 261098d. safe_chat() wraps all Ollama calls. R8 path guard, R1 network guard, R11 provider scrub all active. /violations command live. 19 tests passing.
- Latest commit: `e533073`
- Stage D portfolio analysis: âœ… COMPLETE â€” all four properties analysed. Charters written 2026-04-15. See `AI_Capital_Group_Property_Charters_StageE.docx` (root folder).
- Stage D (Operational Signals â†’ GREEN): âœ… COMPLETE â€” 2026-04-15. Diagnosed 5 false-RED/AMBER signals. Patched phase2_crews.py (off-hours logic, log fallbacks, watching-vs-trading distinction). Updated targets.yaml research cadence. Added health/division_health.py. Two consecutive GREEN briefs confirmed. 23/23 tests passing.
- Stage G (Commercial Division): âœ… COMPLETE â€” 2026-04-15. commercial.py (finance_report, risk_check, score_initiative, run_commercial_division). commercial_division.yaml. /commercial + /score_initiative Telegram commands. Codex review: 8 issues resolved including HIGH inverted-threshold bug. 45/45 tests passing. commit 1367323.
- Stage J (Content Studio - light): âœ… COMPLETE â€” 2026-04-17. Added content_studio crew + orchestration, phase2 division integration, Telegram `/content` + `/content_status`, strict `PENDING_CEO_APPROVAL` gating, and content_studio KPI targets. Two consecutive phase2 runs returned content_studio=GREEN. 14/14 new tests passing. Commit 9e7323d.
- Stage I (Steady State + Developer Tool + Time-Saved Proof): âœ… COMPLETE â€” 2026-04-17. Added Developer Tool (`/develop`, `/develop_approve`, `/develop_deny`, `/develop_status`) with R8 scope gate and R5 CEO approval workflow, semantic memory initialization (nomic-embed-text), time-saved tracking with R9 guardrail proof at 6.25 hours/week (GREEN). 35/35 tests passing. Commit 4b9fc36.
- Stage I (Steady State + Developer Tool): âœ… COMPLETE â€” 2026-04-17. Added `scripts/developer_tool.py`, Telegram developer commands, semantic memory initialization, and time-saved tracking (`scripts/time_tracking.py`). Two-week simulation confirms 6.25 hours/week saved (R9 threshold 5 hours/week).

---

### 11.1  Stage D â€” Integration Readiness Sprint

> **What Stage D means:** The holding company monitoring layer cannot function correctly until all four portfolio properties are cleanly wired into `projects.yaml` and feeding real data. Stage D is complete when the monitoring dashboard shows four green property signals simultaneously for the first time. Until that happens, G1 is not unblocked and Stage G, E, J, K cannot start.
>
> **Analysis done:** Full codebase read of all four properties completed 2026-04-15. Property charters written (see `AI_Capital_Group_Property_Charters_StageE.docx` in root). All gaps and decisions locked. Sprint tasks below are the execution of those findings.

**Stage D definition of done (all must be âœ… before Stage D closes):**

- [ ] `projects.yaml` paths correct for all four properties â€” no OneDrive drift
- [ ] Holding company monitoring green for all four properties for 14 consecutive days
- [ ] Umami analytics live on FreeGhostTools (all 23 pages)
- [ ] FreeGhostTools `about.html` false AdSense claim removed
- [ ] FreeTraderHub OG/Twitter meta "no ads" copy updated
- [ ] Polymarket SSH `aicg_ro@167.234.219.208` returns exit code 0
- [ ] MT5 `runtime_events.jsonl` readable by monitoring layer, signal entries present within last 7 days

**Sprint tasks â€” ordered by dependency, complete top to bottom:**

#### Block 1 â€” projects.yaml Path Corrections *(do first â€” everything depends on this)*

| # | Task | Property | Est. |
|---|------|----------|------|
| 1.1 | Update `local_project_path` for `freeghosttools` to actual location of `free-utility-tools` | FreeGhostTools | 5 min |
| 1.2 | Split FreeTraderHub into two `projects.yaml` entries: `finance_web_page` (website) and `free-traderhub-research-team` (Researcher) â€” correct both paths | FreeTraderHub | 10 min |
| 1.3 | Update `repo_path` for `mt5-agentic-desk` to actual location | MT5 | 5 min |
| 1.4 | Confirm Polymarket `repo_path` is still correct (no change expected) | Polymarket | 2 min |

#### Block 2 â€” Messaging Conflicts *(must land before any monetization work)*

| # | Task | Property | Est. |
|---|------|----------|------|
| 2.1 | Remove false AdSense claim from `about.html`. Replace with forward-looking neutral copy. | FreeGhostTools | 10 min |
| 2.2 | Remove dead Grammarly placeholder affiliate link from all HTML files (contains literal `AFFILIATE_ID`) | FreeGhostTools | 15 min |
| 2.3 | Remove Canva placeholder reference in `compress-image.html` | FreeGhostTools | 5 min |
| 2.4 | Update OG description + Twitter meta on FreeTraderHub â€” remove "no ads" language | FreeTraderHub | 10 min |

#### Block 3 â€” Analytics Gap

| # | Task | Property | Est. |
|---|------|----------|------|
| 3.1 | Add Umami snippet to all 23 HTML pages in `free-utility-tools` | FreeGhostTools | 30 min |
| 3.2 | Add `data-umami-event` to NordVPN affiliate link clicks on all relevant pages | FreeGhostTools | 10 min |

#### Block 4 â€” Polymarket SSH

| # | Task | Property | Est. |
|---|------|----------|------|
| 4.1 | Run `ssh -vvv aicg_ro@167.234.219.208` â€” identify failure class (auth / firewall / key / host key) | Polymarket | 10 min |
| 4.2 | Apply fix per failure class identified in 4.1 | Polymarket | 15â€“30 min |
| 4.3 | Confirm systemd service active and `paper_trades.csv` exists on VPS | Polymarket | 5 min |

#### Block 5 â€” MT5 Signal Verification

| # | Task | Property | Est. |
|---|------|----------|------|
| 5.1 | Check `logs/runtime/runtime_events.jsonl` â€” confirm at least one signal evaluation in last 7 trading days | MT5 | 10 min |
| 5.2 | Confirm all 8 strategies in `library/strategies.json` are at active/approved status | MT5 | 5 min |

**Total estimated effort: 3â€“4 hours**

**Stage D closed:** âœ… 2026-04-15. Trading=GREEN, Websites=GREEN, 23/23 tests, commit e533073. G1 unblocked.

---

### 11.3  Stage H â€” Holding Board v2 + Board Pack Upgrade

> **What Stage H delivers:** The Holding Board v2 upgrades the CEO layer (Phase 3) to produce
> a properly structured Board Pack â€” all 8 required fields per decision item (Â§8), a Dissent
> agent that must file one objection minimum, Commercial division data wired into the CEO brief,
> and MA enforcement that blocks any incomplete Board Pack item from reaching the CEO.
>
> **Why now:** Commercial Division is live (Stage G). The CEO layer currently surfaces
> non-GREEN KPI items as simple approval requests. With Commercial data now available,
> the board brief can include initiative scoring, ROI projections, and risk flags inline â€”
> making every decision the CEO sees a properly scoped Board Pack item, not a raw alert.

**Stage H definition of done:**

- [ ] `crews/holding_ceo.yaml` â€” Dissent agent added; CEO task template updated to include Commercial data
- [ ] `scripts/phase3_holding.py` â€” `_build_board_review()` upgraded to 8-field Board Pack format
- [ ] `scripts/phase3_holding.py` â€” Commercial division status integrated into `_score_company()` and CEO brief
- [ ] `scripts/phase3_holding.py` â€” new `board_pack` mode added (alongside `heartbeat` and `board_review`)
- [ ] MA gate â€” Board Pack items missing any of the 8 fields blocked before reaching CEO
- [ ] Two consecutive Board Pack runs produce complete 8-field output with Dissent filed
- [ ] All existing tests still passing; new Board Pack tests added

**See `STAGE_H_PROMPTS.md` for Claude Code execution prompts.**

---

### 11.2  Stage G â€” Commercial Division

> **What Stage G delivers:** The Commercial Division is the business-management brain of the holding company. It replaces Treasury. It answers four questions every week: Should we do this? What is the expected payoff? What does success look like numerically? Was it worth it afterward?
>
> **G1 is now unblocked.** Stage D is complete. This is the next item on the critical path.
>
> **Guardrail:** G2 â€” one new division at a time. Do not start Stage E (Research) until Stage G is stable and green.

**Stage G definition of done:**

- [ ] `crews/commercial_division.yaml` created â€” manager + finance + analyst + risk agents
- [ ] `scripts/commercial.py` created â€” four sub-functions wired to real data sources
- [ ] `config/projects.yaml` â€” commercial division section added
- [ ] `config/targets.yaml` â€” commercial KPI thresholds added
- [ ] Phase 2 orchestration (`scripts/phase2_crews.py`) â€” commercial crew integrated
- [ ] Telegram commands wired: `/commercial`, `/score <initiative>`
- [ ] Commercial division reports GREEN in two consecutive daily briefs
- [ ] All existing tests still passing; new commercial tests added

**Sub-functions (per Â§9):**

| Sub-function | What it does | Data source |
|---|---|---|
| Finance Reporting | Daily PNL roll-up, weekly P&L statement | MT5 + Polymarket logs |
| Business Case | Go/no-go scoring for new initiatives (per Â§8 Board Pack fields) | CEO-submitted goal text |
| ROI & Impact | Projection, scoring, prioritisation, scenario modelling | Historical brief data |
| Risk Monitoring | Drawdown alerts, cost spike detection, exposure flags | config/targets.yaml thresholds |

**See `STAGE_G_PROMPTS.md` for Claude Code execution prompts.**

---

### 11.8  Stage L â€” FreeTraderHub Prop-Firm Pivot

**Status:** ðŸŸ¡ IN PROGRESS â€” approved 2026-04-18.  
**Duration:** 90 days. **Value readiness:** 2026-06-17 (Day 60).  
**Property:** FreeTraderHub (house brand) / Prop Cockpit (product wordmark).  
**Wedge:** Prop firm traders â€” pass the challenge and keep the funded account.  
**Launch firms:** FTMO, MyFundedFX, FundedNext. Rolling expansion M4+.  
**Pro tier:** Month 5 (deferred from Day 1 waitlist).

Full sprint plan, definition of done, success criteria, rolling expansion
schedule, and guardrail matrix:
`STAGE_L_FREETRADERHUB_PIVOT_PLAN.md`

Linked artifacts:
- Property charter (v1): `FREETRADERHUB_CHARTER_v1.md`
- Commercial scoring (SL-FTH-001): `STAGE_L_COMMERCIAL_SCORING_SL-FTH-001.yaml`
- Content Studio brief (CS-L-001): `STAGE_L_CONTENT_BRIEF_CS-L-001.md`
- Board Pack v2 template: `STAGE_L_BOARD_PACK_V2_PROPERTY_PNL_TEMPLATE.md`

Day-90 Go/Kill review: 2026-07-17.

---

## 12. File Structure

```
ai-holding-company/
â”œâ”€â”€ PLAN.md                          â† THIS FILE â€” read first, always
â”œâ”€â”€ SOUL.md                          â† company identity and personality
â”œâ”€â”€ HEAR
