# Agent-Manned SaaS Company Operating Model v1

Date: 2026-05-09

## Purpose

The goal is not to add more scripts, chatbots, or isolated automations. The goal
is to create a fully manned SaaS holding company operated by AI agents: agents
own departments, communicate with each other, escalate to the owner, preserve
institutional memory, and improve the business without waiting for manual
prompting.

The owner should feel like the CEO of a small operating company, not the human
scheduler for a pile of tools.

## North Star

The company should be able to answer, every day:

- What happened?
- What matters?
- Who is handling it?
- What needs the owner?
- What did we learn?
- What will happen next without the owner?

If the system cannot answer those questions, it is not yet a manned company.

## Definition Of Agent-Manned

An agent is real only when it owns a recurring business function.

An agent-manned company has:

- Named roles with clear responsibilities.
- Recurring cadences.
- Inputs each agent watches.
- Outputs each agent produces.
- Communication channels between agents.
- Escalation rules to the owner.
- Authority boundaries.
- Memory obligations.
- Success metrics tied to business value.

Agents are not valuable because they exist. They are valuable when they remove
work from the owner, catch issues earlier, make decisions faster, preserve
context, or increase output quality.

## Desired Future State

The future operating company has four layers.

### 1. Agent Staff

Agent staff own operating functions. Each has a job description, KPI, inbox,
cadence, and escalation rule.

Initial target staff:

| Agent | Owns | Primary value | Authority |
|---|---|---|---|
| Chief of Staff Agent | Company rhythm, daily CEO brief, handoffs, escalation queue | Owner leverage | Approve |
| Quant Research Lead Agent | Strategy hypotheses, research plans, backtest review | Better trading decisions | Guardrail |
| Quant Ops Agent | Data quality, feed health, broker/recon readiness | Fewer live trading surprises | Guardrail |
| Risk Officer Agent | Blocks unsafe trading, publishing, spend, and deployment decisions | Downside protection | Guardrail |
| Growth Lead Agent | Website analytics, traffic anomalies, experiments | Faster growth loops | Auto |
| Editorial Lead Agent | Content briefs, drafts, SEO/brand consistency | Content throughput | Approve |
| Support Lead Agent | Ticket triage, routine draft replies, customer issue patterns | Headcount replacement | Approve |
| Engineering/Ops Agent | Incidents, deploy readiness, bug triage, dashboard health | Reliability and speed | Approve |
| Finance/Admin Agent | Infra cost, subscriptions, cash-relevant admin signals | Cost control | Guardrail |

This is an org design, not a requirement to build all nine agents at once.

### 2. Operating Room

The operating room is where agents communicate with each other and with humans.
Telegram is useful as a pager and command surface, but it is too shallow for a
fully manned company.

Preferred future surface:

- Slack for agent/human communication, threads, channels, decisions, and
  coordination.
- Dashboard for live status and pending owner attention.
- Markdown reports for evidence and reasoning.
- Local state files for machine-readable truth.
- Memory for durable decisions, lessons, and recurring context.

Slack should not be the source of truth. It should be the company office.

Target channels:

| Channel | Purpose |
|---|---|
| `#ceo-briefing` | Daily owner-facing summary and decisions needed |
| `#approvals` | One-click approval/deny items and status changes |
| `#trading-desk` | Strategy research, data quality, backtests, trading ops |
| `#risk-office` | Blocks, objections, unresolved risk |
| `#growth` | Website analytics, experiments, acquisition |
| `#content` | Briefs, drafts, editorial queue |
| `#support` | Ticket triage, customer pain, draft replies |
| `#engineering` | Bugs, deploys, incidents, reliability |
| `#incidents` | Live incident coordination and postmortems |
| `#agent-handoffs` | Cross-agent handoffs and unresolved dependencies |

### 3. Source Of Truth

The operating company needs durable truth outside chat.

| Truth type | Location |
|---|---|
| Current machine state | `state/` |
| Agent outputs | `reports/` |
| Evidence and reviews | `reports/skills/` |
| Decisions | `docs/decisions/` or structured decision state |
| Work items | Existing board/work item state, later GitHub/Linear if justified |
| Operating doctrine | `docs/` |
| Memory | `memory/` plus local vector memory |

Every serious agent action should leave an artifact. Slack can summarize and
link to artifacts; it should not be the only record.

### 4. Owner Interface

The owner should not manage every agent directly.

The owner receives:

- Daily CEO brief.
- Approval queue.
- Exception alerts.
- Weekly portfolio retro.
- "Ask the company" interface.

The owner should mostly decide, correct, and set direction. The agents should
handle routine monitoring, drafting, triage, review, and follow-up.

## Communication Model

Agent communication should be natural on the surface and structured underneath.

The owner should not feel like they are reading database rows or rigid status
templates. The owner should feel like they are talking to a competent Chief of
Staff who knows the company, checks the records before answering, and can show
evidence when asked.

Default CEO-facing communication should be conversational:

> Trading is yellow today, but not because anything live is in danger. Quant
> Ops found stale bars in the research dataset, so Risk is holding the new
> strategy back until the next clean data-quality run. You do not need to
> decide anything yet.

The structured fields still matter, but they should mostly be stored in the
background:

- Status: Green, Yellow, Red, or Blocked.
- Context: what changed.
- Evidence: link or path to artifact.
- Recommendation: what should happen next.
- Owner need: none, approve, decide, clarify, or intervene.
- Handoff: which agent owns next action.

The visible rule is:

- Natural conversation by default.
- Sources available on request.
- Light source references for consequential claims.
- Structured visible format only for approvals, incidents, risk blocks, formal
  reviews, weekly retros, and dashboard cards.

Example flow:

1. Quant Research Lead posts a candidate strategy review in `#trading-desk`.
2. Quant Ops replies conversationally with the data-quality concern.
3. Risk Officer records a structured block, then explains it plainly in thread.
4. Chief of Staff summarizes the decision state naturally in `#ceo-briefing`.
5. Owner sees only the final approval or exception unless they open the thread.

This is how the company becomes manned instead of merely automated: agents talk
like coworkers, but leave durable structured records behind them.

## Truth-Grounded Conversation

Natural communication must still be grounded in the company's stored truth.
Agents should retrieve before answering factual company questions.

The company should distinguish:

- Known: explicitly found in reports, state, decisions, memory, or work items.
- Inferred: a reasonable synthesis from known records.
- Unknown: not present in company records.
- Stale: present, but too old to trust without refresh.

The agent should say when something is unknown or stale instead of smoothing the
gap over with a confident answer.

For CEO interaction, the default answer shape is conversational:

1. Plain-English answer.
2. Short reason when useful.
3. Owner need if any.
4. Evidence only when the decision is consequential or the owner asks.

Example:

> I would not forward-test this yet. The backtest looks promising, but the data
> evidence is incomplete for the test window. Risk is right to hold it. No owner
> decision is needed until Quant Ops reruns the data-quality check.

If the owner asks "show evidence", the agent should switch modes and cite the
specific report, state file, decision, or memory note behind the answer.

## Authority Model

Each agent action must fit one autonomy category.

| Category | Meaning | Examples |
|---|---|---|
| Auto | Agent executes and reports after the fact | Analytics digest, routine monitoring, draft report generation |
| Approve | Agent proposes, owner approves once, agent executes | Content publishing, support replies, low-risk deploys |
| Guardrail | Agent can block, but cannot approve | Trading go-live, risk exceptions, broker recon breaks |

Default authority:

- Trading actions: Guardrail or Approve, never fully Auto.
- Publishing/external communication: Approve.
- Spend, contracts, credentials: Approve or Guardrail.
- Monitoring/reporting: Auto.
- Strategy promotion: Guardrail.
- Support routine replies: Approve until quality is proven.

## Cadence Model

The company should have a rhythm that does not depend on the owner remembering
to ask.

| Cadence | Output |
|---|---|
| Daily morning | CEO brief: company status, red/yellow flags, approvals needed |
| Pre-market | Trading data-quality check |
| Daily close | Trading ops/recon notes when live trading exists |
| Continuous | Incident detection and urgent exceptions |
| Weekly | Growth analytics, portfolio retro, content plan |
| Monthly | Cost review, strategy review, product/business review |

The first milestone is not autonomy. The first milestone is dependable rhythm.

## Value Contribution

The agent company should create value in five ways, in this priority order.

### 1. Headcount Cost

Agents should absorb recurring work that would otherwise require an operator,
analyst, support rep, editor, QA tester, or coordinator.

Examples:

- Daily data-quality check.
- Weekly analytics digest.
- Support ticket triage.
- Content draft preparation.
- Backtest review packet.
- Cost anomaly monitoring.

### 2. Speed

Agents should compress cycle time by doing work as soon as inputs arrive.

Examples:

- Ticket drafted within minutes.
- Backtest reviewed before a human peer is available.
- Traffic anomaly surfaced before the weekly review.
- Broken feed detected before it contaminates strategy decisions.

### 3. Consistency

Agents should apply the same checklist every time.

Examples:

- Every backtest receives adversarial review.
- Every deploy has a pre-deploy checklist.
- Every weekly retro captures decisions and unresolved issues.
- Every content draft checks brand, intent, and SEO basics.

### 4. Institutional Memory

Agents should remember what was tried, what failed, what worked, and why.

Examples:

- Strategy hypotheses and rejection reasons.
- Customer pain patterns.
- SEO experiments and outcomes.
- Incident causes.
- Owner preferences and standing decisions.

### 5. Owner Leverage

The owner should spend less time collecting context and more time making high
quality decisions.

The felt improvement should be:

- Fewer loose threads.
- Fewer repeated explanations.
- Fewer surprises.
- More work moving without prompting.
- More confidence in what is happening.

## Anti-Theater Test

Before creating any new agent, answer:

1. What recurring business function does it own?
2. What input does it watch?
3. What output does it produce?
4. What decision can it make without the owner?
5. What must it escalate?
6. Where does its work live?
7. How will we know it created value?

If these answers are weak, the agent is theater.

## First Operating Slice

The first useful staffed company does not need every role. It needs enough roles
to create the feeling of a working team.

Recommended first slice:

| Agent | Why first |
|---|---|
| Chief of Staff Agent | Converts noise into owner-facing operating rhythm |
| Quant Ops Agent | Protects trading from bad data and operational drift |
| Risk Officer Agent | Provides real guardrails and owner trust |
| Growth Lead Agent | Makes websites legible as businesses |
| Editorial Lead Agent | Turns research into publishable growth assets |
| Engineering/Ops Agent | Keeps systems and deploys reliable |

Support Lead should join as soon as a real support inbox exists. Finance/Admin
should join when cost and cash tracking become reliable enough to monitor.

## First Three Workflows To Prove The Model

### 1. Daily CEO Brief

Owner-facing brief assembled by Chief of Staff from trading, websites, risk,
engineering, and approvals.

Value: owner leverage and consistency.

Success: the owner can understand company status in under five minutes and sees
only real decisions or exceptions.

### 2. Trading Readiness Loop

Quant Ops checks data quality, Quant Research reviews backtests, Risk Officer
blocks unsafe promotion, Chief of Staff escalates only unresolved decisions.

Value: fewer trading mistakes and faster strategy research cycles.

Success: no strategy reaches forward test without data-quality and adversarial
review artifacts.

### 3. Website Growth Loop

Growth Lead spots traffic/content anomalies, Editorial Lead drafts corrective or
growth content, Engineering/Ops handles site issues, Chief of Staff summarizes
decisions.

Value: faster growth and higher content throughput.

Success: weekly growth decisions are made from evidence, not memory.

## What Changes From Current Repo Thinking

Current docs correctly warn against creating agents for their own sake. That
should remain true.

The change is the target state:

- Today: roles are responsibilities that may not require runtime agents.
- Future: some roles become persistent agent employees when they own a business
  function and communicate through the operating room.

This preserves restraint while making room for the owner's actual goal: a
company that feels staffed.

## Design Decisions To Make Before Building

1. Operating room: Slack, Telegram only, or hybrid.
2. Owner interface: Slack daily brief, dashboard, Telegram pager, or all three.
3. Task system: existing board/work item state first, GitHub Issues/Linear later.
4. Memory rule: what every agent must write to memory after decisions.
5. Agent identity: named employees, functional titles, or both.
6. Support source: email, website form, helpdesk, or Slack intake.
7. Website focus: FreeTraderHub first, or include every property.
8. Trading authority: exact line between research, forward test, and live action.

## Recommended Decision

Adopt the following future-state architecture:

- Slack becomes the operating room.
- Telegram remains the urgent owner pager until Slack proves better.
- Markdown reports remain the reasoning layer.
- `state/` remains the machine-readable truth layer.
- `memory/` becomes mandatory for decisions and lessons.
- The first agents are Chief of Staff, Quant Ops, Risk Officer, Growth Lead,
  Editorial Lead, and Engineering/Ops.

Do not build a new agent framework first. Define the company roles, channels,
message contracts, and handoff rules first. Then make the first agent workflow
feel real end to end.

## Bottom Line

The destination is a fully manned SaaS holding company, not a command suite.
The agents need to feel like staff because they own work, communicate clearly,
remember decisions, and reduce the owner's cognitive load. The first build
should prove that feeling with one complete operating slice before multiplying
agents.
