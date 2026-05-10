# NanoClaw Conversation Layer

Status: design accepted, implementation staged
Date: 2026-05-10

## Decision

NanoClaw may be used as the conversational layer for persona chat, but not as
the source of truth, orchestrator, approval engine, scheduler, or tool runner.

The operating layer remains responsible for truth retrieval and authority. The
conversation layer receives a bounded truth packet and returns natural
owner-facing language.

## Target Flow

```text
Owner message
  -> Operating Room API
  -> persona intent classifier
  -> persona scope map
  -> deterministic truth packet
  -> NanoClaw verbalizer
  -> output verifier
  -> Operating Room UI
```

## Hard Boundaries

- NanoClaw must not read the repository directly in the first integration.
- NanoClaw must not receive broad filesystem mounts.
- NanoClaw must not execute tools, write files, approve items, block items, or
  make operating decisions.
- NanoClaw must not treat chat history as truth.
- NanoClaw may only verbalize facts present in the truth packet.
- If the truth packet does not contain evidence, the answer must say what is
  missing.

## Truth Packet Contract

```json
{
  "schema_version": "persona_truth_packet.v1",
  "persona": "chief-of-staff",
  "display_name": "Chief of Staff",
  "intent": "status",
  "user_message": "what needs me?",
  "truth_state": "known",
  "owner_need": "approve",
  "approvals_count": 1,
  "evidence": [],
  "sources": [],
  "unknowns": [],
  "policy": {
    "allowed_claim_source": "truth_packet_only",
    "no_tool_calls": true,
    "no_file_reads": true,
    "no_writes": true
  }
}
```

## Verbalizer Output Contract

```json
{
  "answer": "Natural owner-facing answer.",
  "unsupported_claims": [],
  "evidence_mode": "hidden",
  "confidence": "high"
}
```

## Application To This Repo

The current `scripts/persona_router.py` is a prototype. It should be split by
responsibility:

- Intent: classify whether the owner is asking for role, status, approvals,
  evidence, action, or unknown.
- Truth packet: read allowed local files and produce structured evidence.
- Verbalizer: deterministic fallback today; NanoClaw later.
- Verifier: reject any model response with unsupported claims.

## Rollout

1. Add the truth packet contract and deterministic fallback verbalizer.
2. Keep the Operating Room using fallback verbalization.
3. Add a disabled NanoClaw adapter behind explicit local configuration.
4. Test NanoClaw on Chief of Staff only.
5. Promote Risk Officer only after unsupported-claim checks pass.

## Current Implementation

`scripts/persona_router.py` now builds `persona_truth_packet.v1`.
`scripts/persona_verbalizer.py` runs:

- `deterministic_fallback` as the live verbalizer.
- `nanoclaw_shadow` as an optional local-outbox comparison path.

The NanoClaw shadow path is disabled by default in `config/projects.yaml`.
When enabled, it reads `state/nanoclaw_shadow_outbox.jsonl` and records whether
the shadow answer would have been accepted. It does not change the live answer.

## Local Shadow Test Loop

The current repo includes a local simulator for the NanoClaw outbox contract. It
does not call NanoClaw or any model. It only proves the inbox/outbox/verifier
plumbing.

1. Set `conversation.nanoclaw.mode` to `shadow` in a local test config.
2. Call `persona_chat`; the router appends a truth packet to
   `state/nanoclaw_shadow_inbox.jsonl`.
3. Run:

   ```powershell
   python scripts/tool_router.py nanoclaw_shadow_write
   ```

4. Call `persona_chat` again. The live answer remains `deterministic_fallback`,
   while `shadow_verbalizer` reports whether the candidate was accepted.

The acceptance check requires:

- Matching `packet_id`.
- No `unsupported_claims`.
- Non-empty answer.
