# Operating Room MVP

This is a local front office for the AI Holding Company.

## Rule

Persona conversation accepts free text. The system first builds a deterministic
truth packet from `state/`, `reports/`, and approved memory files. Today, a
deterministic fallback verbalizer turns that packet into text. The future
NanoClaw layer may replace only that verbalizer step.

## Generate Snapshot

```powershell
python scripts/operating_room_snapshot.py
```

## View

For the full operating room, including persona chat, run the local-only server:

```powershell
python scripts/operating_room_server.py --port 8765
```

Then visit:

```text
http://127.0.0.1:8765/operating-room/
```

The static files still open without the server, but persona chat requires the
local `/api/persona-chat` endpoint.

Persona replies include the natural answer plus collapsed evidence rows and
source paths. The chat transcript is display state only; the system does not use
chat history as truth.

See `docs/communication/nanoclaw-conversation-layer.md` for the NanoClaw
conversation-layer contract.

## Shadow Testing

The local NanoClaw shadow simulator can test the inbox/outbox contract without
calling a model:

```powershell
python scripts/tool_router.py nanoclaw_shadow_write
```

This only writes a candidate shadow response. It does not change the live
persona answer.
