# Decision 0001: Agent Operating Room

Date: 2026-05-09

## Decision

Use a staged hybrid operating-room model.

- Current safe surface: existing Telegram/CLI/report/state rails.
- First implementation surface: local `ask_company` Chief of Staff command.
- Preferred future operating room: Slack, after grounded natural conversation
  works locally.
- Telegram remains the urgent owner pager and fallback approval surface until a
  replacement is proven.

## Rationale

The owner wants the company to feel fully manned by agents, with natural
communication among agents and with the owner. Telegram is already the approved
automation interface, but it is not ideal for nuanced agent-to-agent operating
communication. Slack likely fits the future office better, but adding it before
truth-grounded conversation works would risk creating another noisy inbox.

## Consequences

- Build `ask_company` locally first.
- Keep truth in `reports/`, `state/`, `memory/`, and `docs/decisions/`.
- Do not make Slack the source of truth.
- Do not wire Slack until the Chief of Staff spine can answer common company
  questions from stored truth.

## Review Trigger

Revisit after the owner can ask 10 common company questions and gets natural,
grounded answers from local company truth.
