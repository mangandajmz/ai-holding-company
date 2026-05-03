# Closed-Loop Operating Model

The company loop is the file-first MVP backbone for AI Capital Group. It turns
CEO goals into durable operating records instead of leaving work as chat or
monitoring output.

## Loop Shape

Every meaningful company effort should move through:

```text
Goal -> Evidence -> Review -> CEO Approval -> Action -> Measurement -> Improvement
```

The canonical state file is:

```text
state/company_loops.json
```

Human-readable artifacts are written to:

```text
reports/company_loops/
```

## Statuses

- `GOAL_CAPTURED`
- `PLANNING`
- `EVIDENCE_READY`
- `REVIEW_READY`
- `PENDING_CEO_APPROVAL`
- `APPROVED`
- `IN_PROGRESS`
- `MEASUREMENT_READY`
- `DONE`
- `REJECTED`

## Loop Types

- `website_improvement`
- `content`
- `business_initiative`
- `trading_research`
- `operations`

Live trading execution is not part of the MVP loop. Trading loops are research,
risk, evidence, and alert review only.

## CLI Usage

Create a CEO goal:

```powershell
python scripts/tool_router.py loop new --goal "Improve FreeTraderHub calculator clarity" --type website_improvement --division websites
```

Attach evidence:

```powershell
python scripts/tool_router.py loop evidence --loop-id loop_0001 --path reports/phase2_divisions_latest.md --note "Latest website division evidence"
```

Advance to review:

```powershell
python scripts/tool_router.py loop advance --loop-id loop_0001 --recommendation "Run QA pass before any publishing" --measurement-plan "Checklist passes and CEO can review result"
```

Approve or reject:

```powershell
python scripts/tool_router.py loop approve --loop-id loop_0001 --action "Run QA only; no publishing" --note "CEO approved safe QA action"
python scripts/tool_router.py loop reject --loop-id loop_0001 --note "Need clearer ROI"
```

Start, measure, and close:

```powershell
python scripts/tool_router.py loop start --loop-id loop_0001 --note "QA started"
python scripts/tool_router.py loop measure --loop-id loop_0001 --result "QA checklist complete; no publish action taken"
python scripts/tool_router.py loop done --loop-id loop_0001 --result "Closed after CEO review"
```

## Approval Gate

If a loop contains risky terms around trading action, spending, publishing,
deployment, external communication, credentials/API keys, business commitments,
or legal/tax decisions, it moves to `PENDING_CEO_APPROVAL`.

Action cannot start while approval status is `PENDING_CEO_APPROVAL`.

## Boardroom Use

Boardroom transcripts can be attached as evidence:

```powershell
python scripts/tool_router.py loop evidence --loop-id loop_0001 --path reports/boardroom/boardroom_latest.md --note "Boardroom review"
```

This keeps conversation useful without making chat the source of truth.
