#!/usr/bin/env python3
import json
import time
import requests

BASE = "http://localhost:8000/api/v1"

def health():
    r = requests.get("http://localhost:8000/health", timeout=5)
    r.raise_for_status()
    return r.json()

def query(q: str, conv_id: str | None = None):
    payload = {
        "message": q,
        "conversation_id": conv_id,
        "mode": "qa",
        "user_id": "demo_user",
        "include_context": True,
        "max_context_messages": 10,
    }
    r = requests.post(f"{BASE}/chat/query", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()

def main():
    print("Checking health...")
    print(health())

    tests = [
        "What does Section 1 of the BNS say about short title and commencement?",
        "Explain anticipatory bail safeguards under Indian law.",
        "Summarize Article 21 protections relevant to personal liberty.",
    ]
    conv = None
    for i, q in enumerate(tests, 1):
        print(f"\n[{i}] Q: {q}")
        resp = query(q, conv)
        print(f"Answer (truncated): {resp['response'][:300]}...")
        print(f"Citations: {len(resp.get('citations', []))}")
        if not conv:
            conv = resp["conversation_id"]
        time.sleep(0.5)

    # Show conversation history
    r = requests.get(f"{BASE}/chat/conversations/{conv}/history", timeout=10)
    if r.ok:
        data = r.json()
        print(f"\nConversation '{data['title']}' has {data['total_messages']} messages.")
    else:
        print("Could not fetch conversation history.")

if __name__ == "__main__":
    main()

