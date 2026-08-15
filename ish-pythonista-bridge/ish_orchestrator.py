# ish_orchestrator.py
# Run inside iSH (Alpine). Listens on 0.0.0.0:5000 for Groq

from flask import Flask, request, jsonify
import requests
import json
import uuid
from datetime import datetime
from pathlib import Path
import traceback

app = Flask(__name__)

PYTHONISTA_URL = "http://127.0.0.1:9000/native"
MEMORY_PATH = Path("MEMORY.md")
LAST_PACKET_PATH = Path("last_packet.json")

def load_memory():
    if MEMORY_PATH.exists():
        return MEMORY_PATH.read_text(encoding="utf-8")[:2000]
    return ""

def call_pythonista(command_type, payload=None, task="hardware_task", context=None):
    packet = {
        "id": str(uuid.uuid4()),
        "source": "ish",
        "task": task,
        "requires_hardware": True,
        "command": {
            "type": command_type,
            "payload": payload or {}
        },
        "context": context or {"memory_snippet": load_memory()},
        "result": None,
        "status": "pending",
        "error": None
    }

    try:
        r = requests.post(PYTHONISTA_URL, json=packet, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {
            "status": "error",
            "error": f"Pythonista unreachable: {str(e)}",
            "id": packet["id"]
        }

@app.route("/groq-webhook", methods=["POST"])
def handle_groq():
    try:
        data = request.json or {}
        task = data.get("task") or data.get("instruction") or "unspecified"
        requires_hw = data.get("requires_hardware", False)
        command_type = data.get("command_type", "sys_inspect")
        payload = data.get("payload", {})

        linux_result = {
            "ish_status": "processed",
            "task_received": task,
            "timestamp": datetime.now().isoformat()
        }

        hardware_result = None
        if requires_hw or data.get("force_hardware"):
            hardware_result = call_pythonista(
                command_type=command_type,
                payload=payload,
                task=task,
                context={"memory_snippet": load_memory()}
            )

        response = {
            "ish": linux_result,
            "hardware": hardware_result,
            "status": "success" if (not hardware_result or hardware_result.get("status") == "success") else "partial"
        }

        LAST_PACKET_PATH.write_text(json.dumps(response, indent=2), encoding="utf-8")
        return jsonify(response)

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "trace": traceback.format_exc()
        }), 500

@app.route("/health")
def health():
    try:
        r = requests.get("http://127.0.0.1:9000/health", timeout=3)
        py_ok = r.status_code == 200
    except:
        py_ok = False
    return jsonify({
        "ish": "alive",
        "pythonista_reachable": py_ok
    })

@app.route("/memory", methods=["GET", "POST"])
def memory():
    if request.method == "POST":
        content = request.json.get("content", "")
        MEMORY_PATH.write_text(content, encoding="utf-8")
        return jsonify({"status": "written"})
    return jsonify({"memory": load_memory()})

if __name__ == "__main__":
    print("iSH Orchestrator listening on 0.0.0.0:5000")
    print("POST to /groq-webhook")
    app.run(host="0.0.0.0", port=5000, debug=False)
