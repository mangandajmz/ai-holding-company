# Agent-Manned SaaS Company Implementation Plan

Date: 2026-05-09

## Intent

This plan turns the agent-manned SaaS operating model into an implementation
sequence. The goal is to build a company that feels staffed by agents, not a
larger collection of scripts.

The implementation principle is:

> Natural conversation on the surface, structured truth underneath, controlled
> execution through approved rails.

The first milestone is not full autonomy. The first milestone is a dependable
operating rhythm where agents communicate naturally, reference company truth,
leave durable records, and reduce the owner's cognitive load.

## Success Definition

The implementation is working when the owner can ask the company natural
questions and receive grounded answers:

- What needs me today?
- Why is trading yellow?
- What did Growth learn this week?
- Are we ready to forward-test this strategy?
- What are we blocked on?
- What did we try before?

The answer should feel conversational, but the system should be able to cite the
stored truth behind it.

## Non-Negotiables

- Do not create a parallel agent platform before the operating loop is proven.
- Do not make chat the source of truth.
- Do not let agents invent company status, metrics, decisions, revenue, trades,
  approvals, or customer facts.
- Do not auto-execute trading, publishing, spend, credentials, business
  commitments, legal/tax-sensitive work, or external communication.
- Do not replace existing Telegram/CLI/report/state rails until the replacement
  is demonstrably better.
- Do not expose rigid status templates to the owner by default. Store structure
  underneath; communicate naturally.

## Architecture To Build Toward

| Layer | Purpose | First implementation |
|---|---|---|
| Conversation | Natural CEO and agent communication | Chief of Staff chat/command, later Slack |
| Truth retrieval | Ground answers in company records | Reports/state/memory/work-item retriever |
| Agent staff | Own recurring business functions | Chief of Staff, Quant Ops, Risk, Growth, Editorial, Engineering/Ops |
| Durable records | Preserve evidence, decisions, and outputs | `reports/`, `state/`, `memory/`, `docs/decisions/` |
| Execution rails | Run approved actions safely | Existing scripts, approvals, Telegram, later Slack buttons |
| Dashboard | Current company status | Later, after the first loops are trustworthy |

## Rollout Overview

| Phase | Timebox | Goal |
|---|---|---|
| 0. Decision Lock | 1-2 days | Decide surfaces, first agents, and truth rules |
| 1. Contract Layer | Week 1 | Define roles, skills, channels, records, and handoffs |
| 2. Chief of Staff Spine | Weeks 2-3 | Natural CEO interface grounded in stored truth |
| 3. First Staffed Loops | Weeks 3-6 | Daily CEO brief, trading readiness, website growth |
| 4. Operating Room | Weeks 5-7 | Slack or hybrid communication with durable records |
| 5. Execution And Approvals | Weeks 6-9 | One-click approval flow and follow-through |
| 6. Live Operating Rhythm | Weeks 8-12 | Move shadow loops to live where safe |
| 7. Expansion | Post-90 days | Support, Finance/Admin, broker recon, dashboard depth |

Phases can overlap, but each phase has a gate. If a gate fails, do not widen the
system; fix the loop.

## Phase 0: Decision Lock

Timebox: 1-2 days.

Purpose: remove ambiguity before building.

Decisions to make:

1. Operating room: Slack-first, Telegram-first, or hybrid.
2. CEO interface: Slack DM/channel, Telegram, local CLI, dashboard chat, or a
   staged combination.
3. First agent identities: functional titles only or named staff personas.
4. First business focus: FreeTraderHub only for websites, or all properties.
5. Support source: defer until inbox exists, or choose a support intake now.
6. Trading boundary: exact meaning of research, forward test, paper, and live.
7. Memory rule: what must be written after decisions, blocks, and lessons.

Deliverables:

- Edit `docs/agent-manned-saas-operating-model-v1.md` with locked decisions.
- Create `docs/decisions/0001-agent-operating-room.md`.
- Create `docs/decisions/0002-agent-authority-boundaries.md`.

Gate:

- The owner can explain, in one minute, where agents talk, where truth lives,
  what they can do, and what they must escalate.

## Phase 1: Contract Layer

Timebox: Week 1.

Purpose: define the company before adding runtime.

Files to create:

- `docs/agents/README.md`
- `docs/agents/chief-of-staff.md`
- `docs/agents/quant-ops.md`
- `docs/agents/risk-officer.md`
- `docs/agents/growth-lead.md`
- `docs/agents/editorial-lead.md`
- `docs/agents/engineering-ops.md`
- `docs/skills/README.md`
- `docs/communication/natural-agent-communication.md`
- `docs/communication/truth-grounding-rules.md`
- `docs/communication/handoff-rules.md`

Files to edit:

- `docs/AGENT_ROLE_MODEL.md`
- `docs/DAILY_OPERATING_SYSTEM.md`
- `docs/STRUCTURE_MAP.md`
- `README_TELEGRAM_BRIDGE.md`

Key design:

- Agent docs define job, cadence, inputs, outputs, authority, escalation, memory
  obligations, and success metrics.
- Communication docs define natural language style for CEO-facing answers.
- Structured records are defined as sidecar state/report data, not as the
  default visible message format.

Gate:

- Every first-wave agent has a clear business function and value metric.
- The anti-theater test passes for every first-wave agent.
- No runtime agents are added just because a role exists.

## Phase 2: Chief of Staff Spine

Timebox: Weeks 2-3.

Purpose: create one natural owner-facing front door to the company.

First behavior:

- Owner asks natural questions.
- Chief of Staff retrieves relevant reports, state, memory, approvals, and
  decisions.
- Chief of Staff answers conversationally.
- Chief of Staff cites sources when asked or when the answer is consequential.
- Unknown and stale information are called out plainly.

Files to create:

- `scripts/org_truth_retriever.py`
- `scripts/chief_of_staff.py`
- `tests/test_org_truth_retriever.py`
- `tests/test_chief_of_staff.py`
- `reports/chief_of_staff/README.md`

Files to edit:

- `scripts/tool_router.py`
- `scripts/aiogram_bridge.py` only if Telegram is used for the first surface.

Candidate command:

```powershell
python scripts/tool_router.py ask_company --question "What needs me today?"
```

Design constraints:

- Retrieval must happen before factual answers.
- Answers must classify facts as known, inferred, unknown, or stale internally.
- Sources are available without making every normal answer feel like an audit.
- No external network calls without explicit approval.

Gate:

- The owner can ask 10 common company questions and get useful, natural,
  grounded answers.
- The system refuses or qualifies answers when truth is missing.
- The interaction feels better than reading raw reports.

## Phase 3: First Staffed Loops

Timebox: Weeks 3-6.

Purpose: make the company feel staffed through three complete operating loops.

### Loop 1: Daily CEO Brief

Agents involved:

- Chief of Staff
- Risk Officer
- Growth Lead
- Quant Ops
- Engineering/Ops

Files to create or adapt:

- `docs/skills/risk-aggregate-daily.md`
- `scripts/skill_risk_aggregate_daily.py` or a thin alias over
  `scripts/phase3_holding.py`
- `reports/skills/risk-aggregate-daily/`

Output:

- Natural CEO-facing daily brief.
- Structured sidecar with status, evidence, owner needs, and agent handoffs.

Gate:

- Owner can read the daily brief in under five minutes.
- It contains only real issues, decisions, and useful context.
- Every consequential claim links to retrievable truth.

### Loop 2: Trading Readiness

Agents involved:

- Quant Ops
- Quant Research Lead
- Risk Officer
- Chief of Staff

Files to create or adapt:

- `docs/skills/data-quality-daily.md`
- `docs/skills/backtest-review.md`
- `docs/skills/pre-deploy-checklist.md`
- `scripts/skill_data_quality_daily.py`
- `scripts/skill_backtest_review.py`
- `reports/skills/data-quality-daily/`
- `reports/skills/backtest-review/`

Output:

- Data-quality result before trading/research decisions.
- Adversarial backtest review before forward-test.
- Risk block or pass-for-owner-approval.

Gate:

- No strategy reaches forward test without data-quality and backtest review
  artifacts.
- Risk can block, but cannot approve.
- The owner receives natural summaries, not raw checklist dumps.

### Loop 3: Website Growth

Agents involved:

- Growth Lead
- Editorial Lead
- Engineering/Ops
- Chief of Staff

Files to create or adapt:

- `docs/skills/analytics-weekly.md`
- `docs/skills/content-brief-to-draft.md`
- `scripts/skill_analytics_weekly.py`
- Existing `scripts/content_studio.py`
- `reports/skills/analytics-weekly/`
- `reports/skills/content-brief-to-draft/`

Output:

- Weekly FreeTraderHub analytics digest.
- Anomaly explanation.
- Editorial brief or draft.
- Owner approval request only when publishing or external action is needed.

Gate:

- Website status is legible without manually opening every dashboard.
- At least one weekly growth decision is recorded from evidence.
- Drafts remain approval-gated.

## Phase 4: Operating Room

Timebox: Weeks 5-7.

Purpose: move from command/report interaction to a company office.

Preferred target:

- Slack becomes the operating room.
- Telegram remains urgent pager and fallback approval surface.
- Reports/state remain truth.

Slack channels to create if Slack is chosen:

- `#ceo-briefing`
- `#approvals`
- `#trading-desk`
- `#risk-office`
- `#growth`
- `#content`
- `#support`
- `#engineering`
- `#incidents`
- `#agent-handoffs`

Files to create after explicit Slack decision:

- `docs/communication/slack-operating-room.md`
- `scripts/slack_bridge.py`
- `tests/test_slack_bridge.py`

Files to edit:

- `docs/agent-manned-saas-operating-model-v1.md`
- `README_TELEGRAM_BRIDGE.md`

Gate:

- Agents can post natural updates to the right channel.
- Every update that matters links to a durable artifact.
- Owner can ignore most channels and rely on `#ceo-briefing` plus approvals.

## Phase 5: Execution And Approvals

Timebox: Weeks 6-9.

Purpose: make agent work move to completion without letting agents cross unsafe
boundaries.

Execution model:

1. Agent proposes or executes according to authority.
2. Work item or approval state is created.
3. Owner approves/denies where required.
4. Approved action runs through existing scripts or approved manual rails.
5. Result is recorded.
6. Memory is updated for decisions and lessons.
7. Chief of Staff follows up until closed.

Files to create or adapt:

- `docs/approval-model.md`
- `docs/decisions/0003-agent-execution-boundaries.md`
- `scripts/agent_work_queue.py`
- `tests/test_agent_work_queue.py`
- Existing `state/board_approval_decisions.json`
- Existing `kernel/work_items.py`

Gate:

- Every pending approval has owner, risk, evidence, action, and rollback/close
  path.
- Approved work is followed through to done or blocked.
- Denied work records the reason.

## Phase 6: Live Operating Rhythm

Timebox: Weeks 8-12.

Purpose: flip proven shadow loops into live operating routines.

Candidate live routines:

- Daily CEO brief.
- Data-quality daily.
- Backtest review.
- Weekly analytics digest.
- Content brief-to-draft with approval gate.
- Portfolio retro weekly.

Files to create or adapt:

- `docs/skills/portfolio-retro-weekly.md`
- `scripts/weekly_retro.py`
- `tests/test_weekly_retro.py`
- OS-level scheduled tasks for approved recurring jobs.

Gate:

- The owner feels less need to inspect raw systems.
- Agents surface at least one useful issue, decision, or opportunity per week.
- The weekly retro records decisions, unresolved issues, and follow-through.

## Phase 7: Expansion

Timebox: Post-90 days.

Purpose: add staff only where business inputs exist.

Add Support Lead when:

- A support inbox or intake channel exists.
- Ticket categories are defined.
- Draft reply approval flow exists.
- CSAT or owner-quality review can be tracked.

Add Finance/Admin when:

- Subscription, infra, revenue, and cash-relevant sources are reliable.
- Cost anomaly rules are defined.
- Spend approvals are routed through the approval system.

Add Broker Reconcile when:

- Internal blotter exists.
- Broker export exists.
- Clearing/export source exists if relevant.
- Break resolution workflow exists.

Gate:

- Each new agent replaces real recurring owner work or adds measurable control.

## Milestone Summary

| Milestone | Target | Owner-visible result |
|---|---|---|
| M0 Decision Lock | Day 1-2 | Clear operating-room and authority decisions |
| M1 Agent Contracts | Week 1 | Staff roles feel concrete, not theoretical |
| M2 Ask Company | Week 3 | Natural questions get grounded answers |
| M3 Daily CEO Brief | Week 4 | Company status readable in under five minutes |
| M4 Trading Readiness | Week 6 | Strategy readiness has agent review and risk block |
| M5 Website Growth Loop | Week 6 | Growth and editorial work from evidence |
| M6 Operating Room | Week 7 | Agents communicate naturally in channels/threads |
| M7 Approval Execution | Week 9 | Approved work moves to done and records outcomes |
| M8 Live Rhythm | Week 12 | Company feels staffed week to week |

## Measurement

Track these from the start:

- Owner minutes spent understanding company status.
- Number of owner decisions requested per week.
- Number of useful issues surfaced before the owner noticed.
- Number of agent outputs accepted without major rewrite.
- Number of blocked unsafe actions.
- Number of repeated questions avoided by memory.
- Time from input arriving to agent response.
- Time from approval to completed action.

The subjective metric also matters:

> Does the company feel more manned this week than last week?

If the answer is no, do not add more agents. Improve the communication loop.

## First Build Recommendation

After Phase 0 decisions, build in this order:

1. `docs/agents/` role contracts.
2. `docs/communication/` natural communication and truth-grounding rules.
3. `scripts/org_truth_retriever.py`.
4. `scripts/chief_of_staff.py`.
5. `tool_router.py ask_company`.
6. Daily CEO brief as the first staffed loop.
7. Trading readiness as the first multi-agent guardrail loop.
8. Website growth as the first revenue/growth loop.
9. Slack operating room only after the local conversation loop feels right.

This order keeps the project honest: first prove grounded natural communication,
then add channels, then expand staff.

## Risks

| Risk | Mitigation |
|---|---|
| Agents feel like rigid forms | Natural CEO-facing style; structured records hidden underneath |
| Agents hallucinate status | Retrieval-before-answer; known/inferred/unknown/stale classification |
| Too many agents too early | Anti-theater test and phase gates |
| Slack becomes another noisy inbox | Chief of Staff owns summarization; owner watches briefing and approvals |
| Execution becomes unsafe | Auto/Approve/Guardrail authority and explicit approval rails |
| Memory becomes clutter | Memory writes only for decisions, lessons, recurring facts, and owner preferences |
| Reports become unread | Natural summaries with source links, not raw dumps |

## Code Review Gate For Each Block

Every implementation block must pass the project review gate before the next
block starts:

- Style/lint.
- Logic and edge cases.
- Security and authority boundaries.
- No hardcoded secrets.
- No external network/API assumptions without explicit approval.
- No file writes outside the repo.
- Tests or documented reason tests do not apply.

For documentation-only blocks, review for clarity, consistency, stale
instructions, and mismatch with the operating model.

## Bottom Line

The implementation should not begin with "more agents." It should begin with a
truth-grounded Chief of Staff and three staffed loops that make the company feel
alive: daily CEO brief, trading readiness, and website growth. Once those feel
natural and useful, the operating room and additional agents become leverage
instead of theater.
