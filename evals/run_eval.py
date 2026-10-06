#!/usr/bin/env python3
"""Offline root-cause ranking evaluation over synthetic scenarios."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.agents.state import AgentState  # noqa: E402
from app.agents.workflow import (  # noqa: E402
    _build_hypotheses_deterministic,
    critic_node,
)
from app.services.scenarios import SCENARIOS  # noqa: E402


async def evaluate_one(scenario_id: str, expected: str) -> dict:
    scenario = SCENARIOS[scenario_id]
    state: AgentState = {
        "service_name": scenario.service_name,
        "scenario_id": scenario.id,
        "title": scenario.title,
        "severity": scenario.severity,
        "alert": scenario.alert,
        "logs": scenario.logs,
        "metrics": scenario.metrics,
        "deployments": scenario.deployments,
        "runbooks": [
            {"title": "seed", "content": expected.replace("_", " ") + " " + scenario.description}
        ],
        "trace": [],
    }
    started = time.perf_counter()
    hyps = _build_hypotheses_deterministic(state)
    state["hypotheses"] = hyps
    state = await critic_node(state)
    latency_ms = (time.perf_counter() - started) * 1000
    predicted = state.get("primary_root_cause")
    return {
        "id": scenario_id,
        "expected": expected,
        "predicted": predicted,
        "correct": predicted == expected,
        "evidence_score": state["hypotheses"][0]["evidence_score"] if state.get("hypotheses") else 0,
        "latency_ms": round(latency_ms, 2),
    }


async def main() -> None:
    cases = json.loads((Path(__file__).parent / "scenarios.json").read_text(encoding="utf-8"))
    results = [await evaluate_one(c["id"], c["expected_root_cause"]) for c in cases]
    correct = sum(1 for r in results if r["correct"])
    total = len(results)
    avg_latency = sum(r["latency_ms"] for r in results) / max(total, 1)
    report = {
        "metric": "root_cause_top1_accuracy",
        "dataset_size": total,
        "correct": correct,
        "accuracy": round(correct / total, 3) if total else 0,
        "avg_latency_ms": round(avg_latency, 2),
        "results": results,
    }
    out = Path(__file__).parent / "latest_results.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if correct < total:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
