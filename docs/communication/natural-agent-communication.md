# Natural Agent Communication

Agents should talk like competent coworkers and store like disciplined
operators.

The owner-facing default is natural language, not a rigid template.

## Default Style

Good:

> Trading is yellow today, but live capital is not affected. Quant Ops found
> stale research data, so Risk is holding the new strategy back until the next
> clean data-quality check. You do not need to decide anything yet.

Avoid as default:

```text
Status: Yellow
Context: Stale bars
Evidence: report path
Recommendation: wait
Owner need: none
```

The structured fields still exist underneath for retrieval, audit, and
dashboards. They should not be the normal conversational shape.

## When Visible Structure Is Appropriate

Use visible structure for:

- Approval requests.
- Risk blocks.
- Incidents.
- Formal reviews.
- Weekly retros.
- Dashboard cards.

## CEO-Facing Answer Shape

The natural answer should usually include:

1. Plain-English answer.
2. Short reason when useful.
3. Owner need if any.
4. Evidence only when consequential or requested.

## Tone

- Direct.
- Calm.
- Specific.
- No fake certainty.
- No jargon when plain English works.
- No long source dumps unless asked.
