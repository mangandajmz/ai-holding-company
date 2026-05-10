# Memory Schema

Status: v0

## Purpose

Memory preserves decisions, lessons, recurring facts, owner preferences, and
evidence references so personas and skills do not start from zero.

Memory is context, not proof, unless the row records a decision or standing
instruction. Current operating truth still comes first from `state/`,
`reports/`, `reports/skills/`, and `docs/decisions/`.

## Storage

Current local store:

- `memory/vector_store.jsonl`

Each line should be a JSON object.

## Required Fields

```json
{
  "text": "Human-readable memory text.",
  "metadata": {
    "type": "decision|lesson|owner_preference|fact|artifact_reference",
    "source": "path/or/system",
    "created_at_utc": "2026-05-09T00:00:00+00:00",
    "tags": ["optional", "tags"]
  }
}
```

## Accepted Types

| Type | Meaning |
|---|---|
| `decision` | Owner or authorized operating decision |
| `lesson` | Retrospective learning or repeated pattern |
| `owner_preference` | Stable preference or instruction from the owner |
| `fact` | Durable fact, usually copied from a report |
| `artifact_reference` | Pointer to a report, review, retro, or decision |

## Write Rules

- Write memory for decisions, lessons, recurring facts, and owner preferences.
- Do not write raw secrets, credentials, tokens, payment details, or private
  keys.
- Do not treat chat alone as durable proof.
- Include a source path whenever possible.
- If a fact changes frequently, store the artifact reference rather than a stale
  value.

## Read Rules

- Persona default openings may read memory samples, but must prioritize
  deterministic state and reports.
- Follow-up model calls may use memory only after current state is retrieved.
- If memory conflicts with current reports or state, current reports/state win.

