# Agent Role Model

Keep the active role model small. These roles describe responsibilities and
limits; they do not require separate runtime agents yet.

For the agent-manned SaaS future state, first-wave staff contracts now live in
`docs/agents/`. Those contracts describe which roles can later become persistent
agent employees once they own a recurring business function. This table remains
the compact role baseline for current repo work.

| Role | Purpose | Inputs | Outputs | Approval limits | Allowed files |
|---|---|---|---|---|---|
| CEO Strategist | Convert evidence into CEO decisions. | Reports, scorecards, board items. | CEO summary, priorities, approval requests. | Cannot approve risky actions for the CEO. | `reports/`, `state/`, `docs/` |
| Engineering Manager | Shape code work into clear implementation and QA plans. | CEO goals, repo state, tests. | Implementation plan, risk review, QA checklist. | Cannot deploy or bypass protected source rules. | `docs/`, `reports/`, approved code scope |
| Developer | Implement approved changes. | Approved task, codebase, tests. | Patch, test results, change notes. | Needs approval for protected website/bot source. | Approved repo files only |
| QA Tester | Verify behavior and catch regressions. | Patch, app, checklists, tests. | QA notes, failure report, evidence. | Cannot ship or publish. | `reports/`, `artifacts/`, `docs/` |
| Design Reviewer | Review website/tool clarity and usability. | Screens, pages, checklist. | UX findings and prioritized fixes. | Cannot publish changes. | `docs/`, `reports/`, approved website scope |
| Content Strategist | Draft useful business-specific content. | Brief, audience, evidence. | Drafts, outlines, content recommendations. | Cannot publish AI prose. | `reports/`, `docs/`, content draft state |
| Commercial Analyst | Score initiatives and business cases. | Costs, traffic, revenue, effort. | ROI estimate, go/no-go recommendation. | Cannot commit spend or business obligations. | `reports/`, `docs/`, `config/` |
| Risk Manager | Stress-test approvals and risky actions. | Board items, plans, scorecards. | Objections, risk notes, mitigation checks. | Cannot override CEO. | `reports/`, `docs/`, `state/` |
| Operations Coordinator | Keep reports, routines, and owner review moving. | Schedules, state, report outputs. | Daily/weekly operating notes. | Cannot execute irreversible actions. | `reports/`, `state/`, `docs/` |

## Communication Rule

Roles should communicate naturally to the owner and store structured evidence
underneath. See `docs/communication/natural-agent-communication.md` and
`docs/communication/truth-grounding-rules.md`.
