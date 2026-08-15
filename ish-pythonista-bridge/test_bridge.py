# test_bridge.py
# Run in iSH after Pythonista worker is up

import requests
import json

print("1. health check...")
try:
    r = requests.get("http://127.0.0.1:9000/health", timeout=5)
    print(r.json())
except Exception as e:
    print("FAIL:", e)
    exit(1)

print("\n2. sys_inspect...")
try:
    r = requests.post(
        "http://127.0.0.1:9000/native",
        json={"task": "test", "command": {"type": "sys_inspect"}},
        timeout=8
    )
    print(json.dumps(r.json(), indent=2))
except Exception as e:
    print("FAIL:", e)
