#!/usr/bin/env python3
"""Create one demo incident via the API (API must be running)."""

from __future__ import annotations

import json
import os
import sys
import urllib.request

API_URL = os.getenv("NEXT_PUBLIC_API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "change-me-to-a-strong-secret")
SCENARIO = sys.argv[1] if len(sys.argv) > 1 else "payment-latency-spike"


def main() -> None:
    payload = json.dumps(
        {"scenario_id": SCENARIO, "auto_investigate": True}
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{API_URL}/api/v1/incidents",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": API_KEY,
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    print(json.dumps({"id": data["id"], "status": data["status"], "root_cause": data["root_cause"]}, indent=2))
    print(f"Open: http://localhost:3000/incidents/{data['id']}")


if __name__ == "__main__":
    main()
