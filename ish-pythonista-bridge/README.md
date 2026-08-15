# iSH ←→ Pythonista Bridge

Control flow: **Groq → iSH (Alpine orchestrator) → Pythonista (native/hardware worker)**

## Architecture

- **iSH** listens on `0.0.0.0:5000` for Groq webhooks
- When hardware / native / ctypes work is needed, iSH POSTs a structured packet to Pythonista on `127.0.0.1:9000`
- Pythonista executes and returns the result
- Shared state via `MEMORY.md` + `last_packet.json`

## Files

| File | Where to run |
|------|--------------|
| `ish_orchestrator.py` | iSH (Alpine) |
| `pythonista_worker.py` | Pythonista |

## Quick start

1. Start Pythonista worker first
2. Start iSH orchestrator
3. POST to `http://<phone-ip>:5000/groq-webhook`

```json
{
  "task": "inspect native bridge",
  "requires_hardware": true,
  "command_type": "sys_inspect"
}
```

## Packet schema

```json
{
  "id": "uuid",
  "source": "groq|ish|pythonista",
  "task": "short description",
  "requires_hardware": true,
  "command": {
    "type": "sys_inspect|patch|rag_query|run_code|custom",
    "payload": {}
  },
  "context": {
    "memory_snippet": "",
    "history": []
  },
  "result": null,
  "status": "pending|success|error",
  "error": null
}
```
