# support-triage

## Owner Agent

Support Lead.

## Vertical

Websites.

## Autonomy

Approve until reply quality is proven.

## Purpose

Classify tickets, draft replies for routine issues, and surface customer pain
patterns.

## Current Status

Shadow-mode local runtime exists. A real support inbox is not wired yet.
Until then, the runtime reads optional local intake from
`state/support_tickets.json` and blocks honestly when that file is absent.

Run locally through the Telegram/tool router:

```powershell
python scripts/tool_router.py support_triage
```

## Required Before Runtime

- Ticket source.
- Ticket categories.
- Draft reply approval flow.
- Customer data/privacy boundary.
- Quality review or CSAT signal.

## Outputs

- Ticket category.
- Draft reply.
- Escalation reason.
- Product/content/engineering issue patterns.

## Success Metrics

- Classification accuracy.
- Percent of drafts shipped unedited.
- Response time.
- CSAT delta when available.

## Never

- Never send external replies without approval until quality is proven.
- Never expose customer data outside approved systems.
- Never invent policy, refund, legal, or account details.
