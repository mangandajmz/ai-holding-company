# content-brief-to-draft

## Owner Agent

Editorial Lead.

## Vertical

Websites.

## Autonomy

Approve for publishing. Auto for internal draft creation after a brief exists.

## Purpose

Turn a brief into a useful, brand-consistent, SEO-aware draft while keeping
publishing owner-gated.

## Current Runtime Mapping

- Existing runtime: `scripts/content_studio.py`
- Existing CLI: `python scripts/tool_router.py content_create --brief-text "..."`
- Existing Telegram aliases: `/content`, `/content_status`,
  `/content_approve`, `/content_deny`
- Draft state: `artifacts/content_studio_drafts.jsonl`

## Inputs

- Owner or Growth brief.
- FreeTraderHub research outputs.
- Brand/SEO guidance.
- Prior decisions and owner preferences.

## Outputs

- Draft.
- Draft summary.
- Approval request for publishing.
- Revision or denial record.

## Success Metrics

- Editor time per piece reduced.
- Drafts shipped with fewer major rewrites.
- No AI prose published without explicit approval.

## Never

- Never publish automatically.
- Never invent claims, trading advice, revenue claims, or compliance-sensitive
  statements.
- Never skip owner approval for external communication.
