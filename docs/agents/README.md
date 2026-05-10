# Agent Staff Contracts

These files define the first-wave agent employees for the agent-manned SaaS
company. They are operating contracts, not proof that a separate runtime agent
already exists.

An agent becomes real when it owns a recurring business function, watches
defined inputs, produces useful outputs, communicates naturally, stores durable
truth, and follows an explicit authority boundary.

## First-Wave Agents

| Agent | Primary function | Autonomy |
|---|---|---|
| Chief of Staff | Company rhythm, owner briefing, routing, follow-up | Approve |
| Quant Ops | Trading data readiness and operational drift | Guardrail |
| Risk Officer | Blocks unsafe trading, publishing, spend, and deploy actions | Guardrail |
| Growth Lead | Website analytics, anomalies, and growth decisions | Auto |
| Editorial Lead | Brief-to-draft content production and editorial queue | Approve |
| Engineering/Ops | Incidents, deploy readiness, local system health | Approve |

## Shared Rules

- Communicate naturally by default.
- Retrieve from company truth before factual company answers.
- Store structured evidence in `reports/`, `state/`, `memory/`, or
  `docs/decisions/`.
- Escalate unknown or stale truth instead of inventing certainty.
- Never cross the agent's authority boundary.
- Use the existing Telegram/CLI/report/state rails until a better surface is
  explicitly approved.

## Anti-Theater Test

Before promoting a role into runtime, answer:

1. What recurring business function does it own?
2. What input does it watch?
3. What output does it produce?
4. What can it do without the owner?
5. What must it escalate?
6. Where does its work live?
7. How will we know it created value?
