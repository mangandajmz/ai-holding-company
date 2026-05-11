# Truth-Grounding Rules

Natural communication must be grounded in company truth.

Agents should retrieve before answering factual company questions. The answer
can be conversational, but the facts must come from durable records.

## Truth Sources

Use these before answering company-status questions:

- `reports/daily_brief_latest.*`
- `reports/phase2_divisions_latest.*`
- `reports/phase3_holding_latest.*`
- `reports/skills/`
- `state/`
- `memory/`
- `docs/decisions/`
- Existing work/approval state.

Do not use chat memory alone as proof.

## Truth Labels

Internally classify claims as:

- Known: explicitly present in durable records.
- Inferred: synthesized from known records.
- Unknown: not present in durable records.
- Stale: present but too old to trust without refresh.

## Answer Rules

- Say "I do not know" or "I do not have current evidence" when truth is absent.
- Distinguish fact from recommendation.
- Cite sources when the owner asks "show evidence".
- Include light source references for consequential claims.
- Never invent status, metrics, approvals, revenue, trades, customer facts, or
  decisions.
- Treat memory as context unless it records a decision or standing instruction.

## Staleness

If generated timestamps are missing, malformed, or outside the expected cadence,
call the source stale or unknown instead of treating it as current.
