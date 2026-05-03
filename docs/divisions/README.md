# Division Responsibilities

These responsibilities document the operating model without adding new runtime
agents. Existing crew files remain the source for active agent prompts.

## Executive Division

- Produces CEO summaries, priorities, decisions, approvals, and weekly direction.
- Uses `scripts/phase3_holding.py` and `crews/holding_ceo.yaml`.
- Outputs board packs, priority risks, corrective plays, and approval items.
- Must escalate risky or irreversible work to the CEO.

## Engineering Division

- Handles code tasks, implementation plans, QA checks, release notes, and technical debt.
- Uses the Developer Tool approval flow before code generation or protected edits.
- Outputs plans, patches, test results, and review notes.
- Must not deploy or publish without CEO approval.

## Trading Division

- Produces market watch reports, strategy research, risk checks, and bot health evidence.
- Uses read-only monitoring unless CEO approval explicitly permits a change.
- Outputs trading status, risk flags, and research notes.
- Must never execute live trading actions automatically.

## Marketing Division

- Produces SEO research, traffic growth plans, competitor reviews, and campaign ideas.
- Outputs recommendations that can be scored by Commercial before execution.
- Must not publish external campaigns without CEO approval.

## Content Division

- Produces article drafts, tool descriptions, social posts, and educational content.
- Uses `scripts/content_studio.py` and `crews/content_studio.yaml`.
- Outputs draft artifacts and approval requests.
- Must not publish AI-generated prose without CEO approval.

## Commercial Division

- Produces business feasibility, ROI projections, cost/revenue estimates, and initiative scoring.
- Outputs go/no-go recommendations with evidence, expected upside, cost, confidence, and review date.
- Must score initiatives before they enter execution.

## Operations/Admin Division

- Owns recurring tasks, documentation hygiene, daily/weekly reports, and process improvement.
- Uses `scripts/orchestrator.py`, `scripts/weekly_retro.py`, and Telegram bridge workflows.
- Outputs daily briefs, retros, health status, and process improvement notes.
