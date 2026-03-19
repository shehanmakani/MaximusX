#!/usr/bin/env python3
"""
Maximus-X Sentinel — First-Run Setup Script
=============================================
Run this once after `docker compose up -d` to:
  1. Pull required Ollama models
  2. Verify Qdrant is reachable and create collections
  3. Run a test inference to confirm GPU is being used
  4. Print a summary of what's running

Usage:
  python3 setup.py
"""

import sys
import time
import httpx
import json

OLLAMA_URL = "http://localhost:11434"
QDRANT_URL = "http://localhost:6333"
AGENT_URL  = "http://localhost:8000"

MODELS_REQUIRED = [
    "llama3.2:3b",          # Main reasoning model
    "nomic-embed-text",     # Embeddings for RAG
]

def print_step(n, total, msg):
    print(f"\n[{n}/{total}] {msg}")

def wait_for_service(url, name, timeout=60):
    print(f"  Waiting for {name} at {url}...", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=3)
            if r.status_code < 500:
                print(" ✓")
                return True
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(2)
    print(" ✗ TIMEOUT")
    return False

def pull_model(model_name):
    print(f"  Pulling {model_name}...", end="", flush=True)
    try:
        with httpx.stream("POST", f"{OLLAMA_URL}/api/pull",
                          json={"name": model_name}, timeout=600) as resp:
            for line in resp.iter_lines():
                if line:
                    data = json.loads(line)
                    if data.get("status") == "success":
                        print(" ✓")
                        return True
                    elif "error" in data:
                        print(f" ✗ {data['error']}")
                        return False
    except Exception as e:
        print(f" ✗ {e}")
        return False
    print(" ✓")
    return True

def check_gpu():
    print("  Checking GPU usage...", end="", flush=True)
    try:
        r = httpx.post(f"{OLLAMA_URL}/api/generate",
                       json={"model": "llama3.2:3b", "prompt": "1+1=", "stream": False},
                       timeout=30)
        data = r.json()
        # If eval_duration is fast (<1000ms), GPU is likely being used
        ms = data.get("eval_duration", 0) / 1e6
        if ms < 2000:
            print(f" ✓ {ms:.0f}ms (GPU active)")
        else:
            print(f" ⚠ {ms:.0f}ms (may be CPU — check nvidia runtime)")
    except Exception as e:
        print(f" ✗ {e}")

def test_agent():
    print("  Running end-to-end agent test...", end="", flush=True)
    try:
        r = httpx.post(f"{AGENT_URL}/chat",
                       json={"message": "What is your name?", "channel": "api"},
                       timeout=30)
        reply = r.json().get("reply", "")
        if reply:
            print(f" ✓\n  Reply: {reply[:80]}")
        else:
            print(" ✗ Empty reply")
    except Exception as e:
        print(f" ✗ {e}")

def main():
    print("\n" + "═"*52)
    print("  Maximus-X Sentinel — Setup")
    print("═"*52)

    total = 5
    errors = []

    print_step(1, total, "Checking services are up")
    for url, name, path in [
        (f"{OLLAMA_URL}/api/tags", "Ollama", ""),
        (f"{QDRANT_URL}/healthz", "Qdrant", ""),
        (f"{AGENT_URL}/health", "FastAPI agent", ""),
    ]:
        ok = wait_for_service(url, name)
        if not ok:
            errors.append(f"{name} not reachable at {url}")

    if errors:
        print("\n⚠  Some services didn't start. Check: docker compose logs")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    print_step(2, total, "Pulling Ollama models")
    for model in MODELS_REQUIRED:
        pull_model(model)

    print_step(3, total, "Verifying GPU inference")
    check_gpu()

    print_step(4, total, "Creating Qdrant collections")
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "exec", "maximus-x-server-1",
             "python3", "-m", "app.rag", "ingest"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            print(f"  ✓ {result.stdout.strip()}")
        else:
            print(f"  ⚠ {result.stderr.strip()[:120]}")
    except Exception as e:
        print(f"  ⚠ Run manually: docker exec <server-container> python3 -m app.rag ingest")

    print_step(5, total, "End-to-end agent test")
    test_agent()

    print("\n" + "═"*52)
    print("  Setup complete. Maximus-X Sentinel is live.")
    print("═"*52)
    print(f"\n  Dashboard   : http://localhost:3000")
    print(f"  Agent API   : http://localhost:8000/docs")
    print(f"  Reminders   : http://localhost:8000/reminders")
    print(f"\n  Next steps:")
    print(f"  1. Copy .env.example → .env and fill in tokens")
    print(f"  2. Run: openclaw start  (on Mac)")
    print(f"  3. Run: python3 voice_edge.py  (on Pi 5)")
    print(f"  4. Drop your docs into context_membrane/data/")
    print()

if __name__ == "__main__":
    main()
