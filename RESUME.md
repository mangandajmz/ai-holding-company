# RESUME — AI Holding Company Context Handoff

**Written:** 2026-04-14  
**Purpose:** Session context preservation across Cowork re-mount (OneDrive → Desktop).  
**For any AI agent reading this in a new session:** read this first, then `PLAN.md` (canonical reference), then proceed.

---

## 1. Where We Are

**Stage D — COMPLETE** (commit `e533073`).  
All divisions now GREEN. 23/23 tests passing. Evidence in `reports/stage_d_brief_1.json` and `reports/stage_d_brief_2.json`. Codex review issues resolved.

**Current phase: Stage E-Prep — Property Strategic Reviews.**  
Before building Stage E (Research Division) or Stage G (Commercial Division), CEO directed that each portfolio property must be reviewed for:
1. Implementation quality (is it built well?)
2. Integration fitness (can the holding-co monitor/manage it as-is?)
3. Monetization path (concrete revenue mechanism)
4. Business plan + path to profitability + MVP + growth stages
5. Portfolio contribution (why the holding-co is better *with* this property)
6. Feature audit against the no-overengineering principle (KEEP / CUT / DEFER every feature)

Each review ends with a single **GO / NO-GO / CONDITIONAL-GO** recommendation.

Reviews will live in `strategy/property_reviews/` as one `.md` per property.

## 2. Properties to Review

| # | Property folder | Public name | Type | Status |
|---|-----------------|-------------|------|--------|
| 1 | `free-utility-tools/` | freeghosttools.com | Website (utility tools) | 1 affiliate live, free-first model |
| 2 | `finance_web_page/` | freetraderhub.com | Website (trading tools for retail + prop firm users) | Live, no monetization yet, AI value-add angle |
| 3 | `mt5-agentic-desk/` | MT5 Forex/Gold bot | Trading (desktop) | Live, R2 read-only |
| 4 | `polymarket-bot/` | Polymarket bot | Trading (VPS) | Live (watching mode), R2 read-only |

## 3. CEO Strategic Direction (captured in chat, canonical)

- **Websites:** same playbook — lead with free products, build traffic, establish brand, THEN introduce advanced paid features. No premature monetization.
- **FreeTraderHub positioning:** privacy + free tools for retail traders including prop-firm users currently on premium competitors; AI-driven value-add differentiator before any paywall.
- **FreeGhostTools:** currently one affiliate; path is free → traffic → brand → paid features.
- **Trading bots:** goal is backtesting engines that continuously test new strategies, approved strategies deployed to grow capital, connected to learning models that improve over time.
- **Architecture principle:** the two websites should share the same basic architecture principles.
- **Overall principle:** robust systems, no overengineering, value-add for every feature. CEO works on this daily.

## 4. Constraints from PLAN.md v5 (Non-negotiable)

- **R1** 100% local (Ollama only, no cloud APIs)
- **R2** MT5 + Polymarket bot source = READ-ONLY (no param changes without CEO via Loop)
- **R3** Website source = READ-ONLY except via Developer Tool + CEO approval
- **R4** No auto-publish of AI prose
- **R5** No live money / cost >$50 without CEO
- **R8** Developer Tool scope = `ai-holding-company/` only
- **R11** No OpenClaw / Docker Telegram gateway — python-telegram-bot only
- **Board Pack §8:** every decision must carry 8 fields (rationale, upside, effort/cost, confidence, owner, deadline, dissent, post-launch measurement)
- **G2:** max one new division activated at a time

Business Plan section of each review MUST map to these 8 Board Pack fields so reviews plug directly into Commercial Division when it's built (Stage G).

## 5. Review Template (6 Sections, Locked)

```
# Property Strategic Review — <Name>

## 1. Implementation Snapshot
- Stack / structure / hosting / deploy / analytics
- Verdict: fit / needs-work / rebuild

## 2. Integration Fitness
- Does it emit signals division_health.py needs? (heartbeat, revenue, traffic, uptime)
- Gap list with severity
- Verdict: plug-and-play / small adapter / significant work

## 3. Monetization Engine
- Concrete mechanisms (name the network, the program, the tier)
- Unit economics (realistic, not aspirational)
- Every mechanism must pass "is this a real dollar path?" test

## 4. Business Plan (maps to PLAN §8 Board Pack fields)
- Objective (one sentence)
- Rationale
- Expected upside (quantified)
- Expected effort / cost
- Confidence level (High/Med/Low + one-line reason)
- Owner
- Deadline / review date
- Dissent / counter-argument
- Post-launch measurement plan
- MVP to integrate (smallest version that earns portfolio slot)
- Path to profitability (stages with triggers)
- Growth plan (2-3 stages max, each with metric)

## 5. Portfolio Contribution
- Cross-division value (feeds Research? leads for Trading? diversifies revenue?)
- If thin, property shouldn't be in the portfolio

## 6. Feature Audit (no-overengineering discipline)
- Every existing and proposed feature tagged KEEP / CUT / DEFER
- Reason per tag

## Final Recommendation: GO / NO-GO / CONDITIONAL-GO
- If conditional, name the conditions explicitly
```

## 6. Blockers Resolved This Session

- [X] Located holding-co context docs — read PLAN.md v5, SOUL.md, HEARTBEAT.md, heartbeat.yaml, operating_model_philosophy.md
- [X] Read monitoring tools — `tools/check_website.py`, `tools/read_bot_logs.py`, `tools/system_status.py`
- [ ] **BLOCKED:** property folders (`free-utility-tools`, `finance_web_page`, `mt5-agentic-desk`, `polymarket-bot`) not visible in mount. CEO moving folder from OneDrive to Desktop and re-mounting. **This blocker clears when RESUME.md is read in the new Desktop-mounted session.**
- [ ] **BLOCKED:** live site audit — WebFetch egress proxy blocks freeghosttools.com and freetraderhub.com. In new session, CEO to paste homepage HTML or provide screenshots for live-site cross-check.

## 7. Drift Findings (do NOT fix without CEO approval — list only)

These violate PLAN.md v5 R11 or claim infrastructure that isn't in the mounted folder:

1. `SOUL.md` brief template references `OpenClaw: {running/stopped}` → should be `Telegram gateway`
2. `HEARTBEAT.md` §Available Tools still lists Docker/OpenClaw references
3. `heartbeat.yaml` header: "OpenClaw Heartbeat Schedule" — PLAN §11 says Windows Task Scheduler is the truth
4. `tools/system_status.py` actively checks for Docker + OpenClaw containers — violates R11
5. `tools/check_website.py` has placeholder URLs (`your-website-1.com`, `your-website-2.com`)
6. `tools/read_bot_logs.py` has placeholder paths (`C:\Users\J\bots\forex`, `your-vps-ip`)
7. `docker-compose.yml` present at repo root — violates R11 if used for Telegram gateway
8. SOUL.md says "Phase 1 — Core Monitoring" but PLAN §11 shows Stage D complete
9. Stage D deliverables referenced in chat (`scripts/phase2_crews.py`, `health/division_health.py`, `config/targets.yaml`, `reports/stage_d_brief_*.json`) — **none of these paths exist in current mount**. Either the mount is pointing at an old snapshot, or Stage D was done in a different working tree. Investigate in new session.

**Action:** do not change these. Just log them. CEO decides when/how to clean up (likely a dedicated "Stage D+ — Drift Cleanup" mini-phase).

## 8. Next Session — First 5 Actions

1. Read `RESUME.md` (this file), then `PLAN.md`
2. `ls` the root — confirm 4 property folders are visible
3. `ls` each property folder, read each top-level README / package.json / main entry point / config
4. Confirm Stage D deliverables (`scripts/`, `health/`, `config/targets.yaml`, `reports/`) are present — if not, flag drift finding #9
5. Produce `strategy/property_reviews/_TEMPLATE.md` first, then one review at a time starting with FreeGhostTools (CEO preference — it was the trigger for this phase)

## 9. Outstanding Clarifying Questions for CEO

Unanswered from this session — resolve before or during first review:

- **Output format:** Markdown only, or Markdown + `.docx` render for archival? (My recommendation: MD only — diff-able, version-controllable, agent-readable.)
- **Trading scope:** one review covering MT5 + Polymarket, or two separate reviews? (My recommendation: two separate — different monetization paths, different risks, different learning-loop designs.)
- **Capital budget per property:** roughly how much time/money willing to invest to bring each to MVP-integration state? (Calibrates "path to profitability" realism.)
- **Monetization hard rules:** anything off-limits? (e.g., no email capture, no crypto, no data sales, affiliate-only)

## 10. Git State

Last known commit: `e533073` (Stage D complete). Any uncommitted work in the Desktop copy after the move should be inspected via `git status` before Stage E-Prep writes begin.

---

*End of RESUME.md — when read in a new session, confirm all 4 property folders visible, then proceed to Section 8 action list.*
