# pythonista_worker.py
# Run this in Pythonista. Listens on 127.0.0.1:9000

from bottle import route, run, request, response
import json
import ctypes
import uuid
from pathlib import Path
from datetime import datetime
import clipboard
import console

MEMORY_PATH = Path("MEMORY.md")
LAST_PACKET_PATH = Path("last_packet.json")
INBOX_PATH = Path("inbox")
INBOX_PATH.mkdir(exist_ok=True)

def load_memory():
    if MEMORY_PATH.exists():
        return MEMORY_PATH.read_text(encoding="utf-8")[:3000]
    return ""

def save_packet(packet):
    LAST_PACKET_PATH.write_text(json.dumps(packet, indent=2), encoding="utf-8")

@route("/native", method="POST")
def handle_native():
    try:
        data = request.json or {}
        packet = {
            "id": data.get("id") or str(uuid.uuid4()),
            "source": "pythonista",
            "task": data.get("task", "native_call"),
            "requires_hardware": True,
            "command": data.get("command", {}),
            "context": data.get("context", {}),
            "result": None,
            "status": "pending",
            "error": None,
            "timestamp": datetime.now().isoformat()
        }

        cmd = packet["command"]
        cmd_type = cmd.get("type", "sys_inspect")

        if cmd_type == "sys_inspect":
            try:
                libc = ctypes.CDLL(None)
                packet["result"] = {
                    "native_bridge": "active",
                    "libc": str(libc),
                    "memory_loaded": bool(load_memory())
                }
                packet["status"] = "success"
            except Exception as e:
                packet["status"] = "error"
                packet["error"] = str(e)

        elif cmd_type == "rag_query":
            query = cmd.get("payload", {}).get("query", "")
            mem = load_memory()
            packet["result"] = {
                "query": query,
                "memory_snippet": mem[:800],
                "note": "Full RAG corpus not rebuilt here – use AutonomousAgenticNode for heavy search"
            }
            packet["status"] = "success"

        elif cmd_type == "patch":
            patch_text = cmd.get("payload", {}).get("patch", "")
            if "--- TARGET:" in patch_text:
                packet["result"] = {"applied": True, "message": "Patch block received – integrate with your apply_patch()"}
                packet["status"] = "success"
                clipboard.set(patch_text)
            else:
                packet["status"] = "error"
                packet["error"] = "No valid TARGET patch found"

        elif cmd_type == "run_code":
            code = cmd.get("payload", {}).get("code", "")
            try:
                local_env = {}
                exec(code, {"__builtins__": {}}, local_env)
                packet["result"] = {"output": str(local_env.get("result", "executed"))}
                packet["status"] = "success"
            except Exception as e:
                packet["status"] = "error"
                packet["error"] = str(e)

        else:
            packet["status"] = "error"
            packet["error"] = f"Unknown command type: {cmd_type}"

        save_packet(packet)
        response.content_type = "application/json"
        return json.dumps(packet)

    except Exception as e:
        err = {"status": "error", "error": str(e)}
        response.status = 500
        return json.dumps(err)

@route("/health")
def health():
    return {"status": "alive", "service": "pythonista_worker", "port": 9000}

if __name__ == "__main__":
    print("Pythonista Worker listening on 127.0.0.1:9000")
    console.hud_alert("Worker online", "success", 1.0)
    run(host="127.0.0.1", port=9000, debug=False)
