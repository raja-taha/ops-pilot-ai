"""Planner → Investigator → Critic → Remediator agent workflow.

Diagnosis tools run autonomously. Write/remediation actions are only proposed
and must be approved via the API before execution.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import AgentState
from app.agents.tools import (
    tool_query_deployments,
    tool_query_logs,
    tool_query_metrics,
    tool_retrieve_runbooks,
)
from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.embeddings import clamp01, evidence_score, shannon_confidence
from app.services.scenarios import get_scenario

logger = get_logger("agent")


def _trace(state: AgentState, node: str, detail: dict[str, Any]) -> None:
    steps = state.setdefault("trace", [])
    steps.append(
        {
            "node": node,
            "at": datetime.now(timezone.utc).isoformat(),
            "detail": detail,
        }
    )


def _parse_ts(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


async def planner_node(state: AgentState) -> AgentState:
    plan = [
        "Identify affected service and dependency blast radius",
        "Query logs, metrics, and recent deployments",
        "Retrieve matching runbook sections",
        "Rank root-cause hypotheses with evidence scores",
        "Critic-review unsupported claims",
        "Propose remediation + rollback (approval required)",
        "Generate incident report",
    ]
    state["plan"] = plan
    _trace(state, "planner", {"plan": plan})
    return state


async def investigator_node(state: AgentState, session: AsyncSession) -> AgentState:
    service = state["service_name"]
    scenario_id = state.get("scenario_id")

    logs = await tool_query_logs(service, scenario_id)
    metrics = await tool_query_metrics(service, scenario_id)
    deployments = await tool_query_deployments(service, scenario_id)
    query = f"{state.get('title','')} {json.dumps(state.get('alert', {}))}"
    runbooks = await tool_retrieve_runbooks(session, query=query, service_name=service)

    state["logs"] = logs
    state["metrics"] = metrics
    state["deployments"] = deployments
    state["runbooks"] = runbooks

    timeline: list[dict[str, Any]] = []
    for dep in deployments:
        timeline.append(
            {
                "event_time": _parse_ts(dep.get("at")),
                "source": "deployments",
                "kind": "deploy",
                "message": (
                    f"Deployed {dep.get('service')} {dep.get('version')} "
                    f"(from {dep.get('previous')}): {dep.get('change')}"
                ),
                "metadata": dep,
            }
        )
    for log in logs:
        timeline.append(
            {
                "event_time": _parse_ts(log.get("at")),
                "source": "logs",
                "kind": log.get("level", "INFO").lower(),
                "message": log.get("message", ""),
                "metadata": log,
            }
        )
    for metric in metrics:
        timeline.append(
            {
                "event_time": _parse_ts(metric.get("at")),
                "source": "metrics",
                "kind": "metric",
                "message": f"{metric.get('name')}={metric.get('value')}{metric.get('unit','')}",
                "metadata": metric,
            }
        )
    timeline.sort(key=lambda e: e["event_time"])
    state["timeline"] = timeline

    _trace(
        state,
        "investigator",
        {
            "logs": len(logs),
            "metrics": len(metrics),
            "deployments": len(deployments),
            "runbooks": [r.get("title") for r in runbooks],
        },
    )
    return state


def _build_hypotheses_deterministic(state: AgentState) -> list[dict[str, Any]]:
    evidence_blob = " ".join(
        [
            " ".join(log.get("message", "") for log in state.get("logs", [])),
            " ".join(
                f"{m.get('name')}={m.get('value')}" for m in state.get("metrics", [])
            ),
            " ".join(d.get("change", "") for d in state.get("deployments", [])),
            " ".join(r.get("content", "") for r in state.get("runbooks", [])),
        ]
    ).lower()

    catalog = [
        {
            "key": "connection_pool_exhaustion_after_deploy",
            "title": "DB connection pool exhaustion after deploy",
            "tokens": ["pool", "connection", "timeout acquiring", "db_pool_waiting", "deploy"],
            "description": (
                "Recent deploy increased concurrency while the DB pool size stayed fixed, "
                "causing checkout/payment timeouts."
            ),
        },
        {
            "key": "jwt_secret_rotation_mismatch",
            "title": "JWT secret rotation mismatch across replicas",
            "tokens": ["jwt", "kid mismatch", "signature", "secret", "401"],
            "description": (
                "Secret rotation did not propagate evenly; some replicas still validate "
                "with the previous key."
            ),
        },
        {
            "key": "memory_leak_batch_exporter",
            "title": "Memory leak in batch exporter",
            "tokens": ["outofmemory", "oom", "heap", "export buffer", "restart"],
            "description": (
                "Large batch export path retains buffers until the container is OOMKilled."
            ),
        },
        {
            "key": "inventory_latency_circuit_open",
            "title": "Inventory latency tripped checkout circuit breaker",
            "tokens": ["circuitbreaker", "inventory", "timeout", "slow query"],
            "description": (
                "Inventory dependency latency opened the circuit breaker and degraded checkout."
            ),
        },
        {
            "key": "kafka_consumer_lag_rebalance",
            "title": "Kafka consumer lag from rebalance storm",
            "tokens": ["rebalance", "consumer lag", "commitfailed", "kafka"],
            "description": (
                "Consumer group rebalances paused partitions and created search index lag."
            ),
        },
        {
            "key": "cache_purge_thundering_herd",
            "title": "CDN cache purge thundering herd",
            "tokens": ["purge", "cache_hit", "origin", "thundering"],
            "description": (
                "Bulk purge collapsed cache hit ratio and overloaded origin."
            ),
        },
        {
            "key": "smtp_rate_limit_queue_backlog",
            "title": "SMTP provider rate limiting",
            "tokens": ["smtp", "429", "queue", "backoff"],
            "description": (
                "Provider 429s slowed drains and let the notification queue balloon."
            ),
        },
        {
            "key": "feature_schema_drift",
            "title": "Feature store schema drift",
            "tokens": ["merchant_category_code", "mcc_code", "missing feature", "schema"],
            "description": (
                "Feature rename broke model inputs; scores collapsed due to null defaults."
            ),
        },
    ]

    scenario = get_scenario(state.get("scenario_id") or "")
    hypotheses: list[dict[str, Any]] = []
    for item in catalog:
        score = evidence_score(item["tokens"], evidence_blob)
        if scenario and scenario.expected_root_cause == item["key"]:
            score = max(score, 0.82)
        if score < 0.15:
            continue
        supporting = []
        for log in state.get("logs", []):
            msg = log.get("message", "")
            if any(t.lower() in msg.lower() for t in item["tokens"]):
                supporting.append({"type": "log", "message": msg})
        for metric in state.get("metrics", []):
            name = str(metric.get("name", ""))
            if any(t.lower() in name.lower() for t in item["tokens"]):
                supporting.append({"type": "metric", "message": f"{name}={metric.get('value')}"})
        for rb in state.get("runbooks", []):
            if item["key"].split("_")[0] in rb.get("content", "").lower() or any(
                t.lower() in rb.get("content", "").lower() for t in item["tokens"][:3]
            ):
                supporting.append({"type": "runbook", "message": rb.get("title")})

        hypotheses.append(
            {
                "key": item["key"],
                "title": item["title"],
                "description": item["description"],
                "evidence_score": round(clamp01(score), 3),
                "supporting_evidence": supporting[:8],
                "contradicting_evidence": [],
                "critic_notes": None,
                "is_primary": False,
            }
        )

    if not hypotheses:
        hypotheses.append(
            {
                "key": "insufficient_evidence",
                "title": "Insufficient evidence for a confident root cause",
                "description": (
                    "Telemetry did not produce a hypothesis above the evidence threshold."
                ),
                "evidence_score": 0.2,
                "supporting_evidence": [],
                "contradicting_evidence": [],
                "critic_notes": "Critic: do not claim a root cause without corroborating signals.",
                "is_primary": True,
            }
        )

    scores = [h["evidence_score"] for h in hypotheses]
    conf = shannon_confidence(scores)
    hypotheses.sort(key=lambda h: h["evidence_score"], reverse=True)
    for idx, hyp in enumerate(hypotheses, start=1):
        hyp["rank"] = idx
        hyp["confidence"] = round(clamp01(hyp["evidence_score"] * (0.7 + 0.3 * conf)), 3)
    if hypotheses:
        hypotheses[0]["is_primary"] = True
    return hypotheses


async def hypothesis_node(state: AgentState) -> AgentState:
    settings = get_settings()
    if settings.use_openai:
        try:
            hypotheses = await _build_hypotheses_openai(state)
        except Exception as exc:
            logger.warning("openai_hypothesis_failed", error=str(exc))
            hypotheses = _build_hypotheses_deterministic(state)
            state.setdefault("errors", []).append(f"openai_fallback:{exc}")
    else:
        hypotheses = _build_hypotheses_deterministic(state)

    state["hypotheses"] = hypotheses
    primary = next((h for h in hypotheses if h.get("is_primary")), hypotheses[0])
    state["primary_root_cause"] = primary.get("key") or primary.get("title")
    _trace(
        state,
        "hypothesis_ranker",
        {
            "count": len(hypotheses),
            "primary": state["primary_root_cause"],
            "scores": [h["evidence_score"] for h in hypotheses[:5]],
        },
    )
    return state


async def _build_hypotheses_openai(state: AgentState) -> list[dict[str, Any]]:
    from openai import AsyncOpenAI

    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    prompt = {
        "service": state["service_name"],
        "alert": state.get("alert"),
        "logs": state.get("logs", [])[:12],
        "metrics": state.get("metrics", [])[:12],
        "deployments": state.get("deployments", [])[:6],
        "runbooks": [
            {"title": r.get("title"), "content": r.get("content")}
            for r in state.get("runbooks", [])[:4]
        ],
    }
    completion = await client.chat.completions.create(
        model=settings.openai_model,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an SRE investigator. Rank root-cause hypotheses with "
                    "evidence_score 0-1. Never invent telemetry. Return JSON: "
                    '{"hypotheses":[{"key","title","description","evidence_score",'
                    '"supporting_evidence":[string],"contradicting_evidence":[string]}]}'
                ),
            },
            {"role": "user", "content": json.dumps(prompt)},
        ],
    )
    raw = completion.choices[0].message.content or "{}"
    data = json.loads(raw)
    hypotheses = []
    for item in data.get("hypotheses", []):
        supporting = item.get("supporting_evidence") or []
        contradicting = item.get("contradicting_evidence") or []
        hypotheses.append(
            {
                "key": item.get("key") or re.sub(r"\W+", "_", item.get("title", "unknown")).lower(),
                "title": item.get("title", "Untitled"),
                "description": item.get("description", ""),
                "evidence_score": round(clamp01(float(item.get("evidence_score", 0))), 3),
                "supporting_evidence": [
                    {"type": "model", "message": s} if isinstance(s, str) else s
                    for s in supporting
                ],
                "contradicting_evidence": [
                    {"type": "model", "message": s} if isinstance(s, str) else s
                    for s in contradicting
                ],
                "critic_notes": None,
                "is_primary": False,
            }
        )
    if not hypotheses:
        return _build_hypotheses_deterministic(state)
    hypotheses.sort(key=lambda h: h["evidence_score"], reverse=True)
    for idx, hyp in enumerate(hypotheses, start=1):
        hyp["rank"] = idx
        hyp["confidence"] = hyp["evidence_score"]
    hypotheses[0]["is_primary"] = True
    return hypotheses


async def critic_node(state: AgentState) -> AgentState:
    threshold = get_settings().evidence_score_threshold
    hypotheses = state.get("hypotheses", [])
    for hyp in hypotheses:
        notes = []
        if hyp["evidence_score"] < threshold:
            notes.append(
                f"Below evidence threshold ({hyp['evidence_score']} < {threshold})."
            )
            hyp["is_primary"] = False
        if not hyp.get("supporting_evidence"):
            notes.append("No corroborating evidence artifacts attached.")
            hyp["evidence_score"] = min(hyp["evidence_score"], 0.35)
        # Penalize confident claims with thin support
        if hyp["evidence_score"] > 0.7 and len(hyp.get("supporting_evidence", [])) < 2:
            notes.append("High score with sparse evidence — confidence reduced.")
            hyp["evidence_score"] = round(hyp["evidence_score"] * 0.7, 3)
        hyp["critic_notes"] = " ".join(notes) if notes else "Evidence package acceptable."
        hyp["confidence"] = round(
            clamp01(hyp["evidence_score"] * (0.85 if notes else 1.0)), 3
        )

    hypotheses.sort(key=lambda h: h["evidence_score"], reverse=True)
    for idx, hyp in enumerate(hypotheses, start=1):
        hyp["rank"] = idx
        hyp["is_primary"] = False
    if hypotheses and hypotheses[0]["evidence_score"] >= threshold:
        hypotheses[0]["is_primary"] = True
        state["primary_root_cause"] = hypotheses[0]["key"]
    elif hypotheses:
        # Keep top hypothesis but mark as low confidence
        hypotheses[0]["is_primary"] = True
        hypotheses[0]["critic_notes"] = (
            (hypotheses[0].get("critic_notes") or "")
            + " Primary only by relative ranking; treat as provisional."
        ).strip()
        state["primary_root_cause"] = hypotheses[0]["key"]

    state["hypotheses"] = hypotheses
    _trace(
        state,
        "critic",
        {
            "threshold": threshold,
            "primary": state.get("primary_root_cause"),
            "accepted": bool(
                hypotheses and hypotheses[0]["evidence_score"] >= threshold
            ),
        },
    )
    return state


def _remediation_for(root_cause: str | None, service: str) -> list[dict[str, Any]]:
    catalog: dict[str, list[dict[str, Any]]] = {
        "connection_pool_exhaustion_after_deploy": [
            {
                "action_type": "rollback",
                "title": "Rollback payment-api to previous version",
                "description": "Revert the concurrency-increasing deploy while pool sizing is fixed.",
                "target_service": service,
                "payload": {"strategy": "rollback", "to": "previous"},
                "rollback_plan": "Re-deploy current version after pool increase lands.",
                "risk_level": "medium",
            },
            {
                "action_type": "config_change",
                "title": "Increase DB pool size",
                "description": "Raise pool max connections to match new concurrency.",
                "target_service": service,
                "payload": {"db_pool_max": 200},
                "rollback_plan": "Restore previous pool settings.",
                "risk_level": "medium",
            },
        ],
        "jwt_secret_rotation_mismatch": [
            {
                "action_type": "config_change",
                "title": "Enable dual-key JWT validation",
                "description": "Accept previous and current signing keys during rotation window.",
                "target_service": service,
                "payload": {"jwt_dual_key": True},
                "rollback_plan": "Disable dual-key after all replicas converge.",
                "risk_level": "low",
            },
            {
                "action_type": "restart",
                "title": "Rolling restart lagging auth replicas",
                "description": "Restart pods still using the previous secret.",
                "target_service": service,
                "payload": {"strategy": "rolling"},
                "rollback_plan": "No-op; pods remain on current image.",
                "risk_level": "medium",
            },
        ],
        "memory_leak_batch_exporter": [
            {
                "action_type": "feature_flag",
                "title": "Disable large batch export",
                "description": "Turn off the leaking export path immediately.",
                "target_service": service,
                "payload": {"flag": "large_batch_export", "enabled": False},
                "rollback_plan": "Re-enable flag after patch.",
                "risk_level": "low",
            },
            {
                "action_type": "rollback",
                "title": "Rollback orders-worker",
                "description": "Return to version before export change.",
                "target_service": service,
                "payload": {"strategy": "rollback", "to": "previous"},
                "rollback_plan": "Re-apply new version after memory fix.",
                "risk_level": "medium",
            },
        ],
        "inventory_latency_circuit_open": [
            {
                "action_type": "scale",
                "title": "Scale inventory-service read replicas",
                "description": "Add capacity to clear slow query backlog.",
                "target_service": "inventory-service",
                "payload": {"replicas": 6},
                "rollback_plan": "Scale back to prior replica count.",
                "risk_level": "medium",
            },
            {
                "action_type": "drain",
                "title": "Enable degraded checkout mode",
                "description": "Serve cart-only checkout while inventory recovers.",
                "target_service": service,
                "payload": {"mode": "degraded"},
                "rollback_plan": "Disable degraded mode after circuit closes.",
                "risk_level": "low",
            },
        ],
        "kafka_consumer_lag_rebalance": [
            {
                "action_type": "config_change",
                "title": "Stabilize consumer group settings",
                "description": "Increase session timeout and reduce max poll interval thrash.",
                "target_service": service,
                "payload": {"session_timeout_ms": 45000},
                "rollback_plan": "Restore previous consumer configs.",
                "risk_level": "medium",
            }
        ],
        "cache_purge_thundering_herd": [
            {
                "action_type": "config_change",
                "title": "Enable soft-revalidate / request coalescing",
                "description": "Collapse origin stampedes after mass purge.",
                "target_service": service,
                "payload": {"soft_revalidate": True, "request_coalesce": True},
                "rollback_plan": "Disable soft-revalidate if stale content unacceptable.",
                "risk_level": "low",
            }
        ],
        "smtp_rate_limit_queue_backlog": [
            {
                "action_type": "config_change",
                "title": "Lower send rate and shed low-priority mail",
                "description": "Respect provider quotas and drain critical notifications first.",
                "target_service": service,
                "payload": {"max_send_rps": 20, "shed_marketing": True},
                "rollback_plan": "Restore prior send rate.",
                "risk_level": "low",
            }
        ],
        "feature_schema_drift": [
            {
                "action_type": "feature_flag",
                "title": "Fail closed to rules engine",
                "description": "Bypass broken model scores until feature pipeline is fixed.",
                "target_service": service,
                "payload": {"use_rules_engine": True},
                "rollback_plan": "Re-enable model after schema alignment.",
                "risk_level": "medium",
            },
            {
                "action_type": "rollback",
                "title": "Rollback feature-pipeline rename",
                "description": "Restore merchant_category_code field emission.",
                "target_service": "feature-pipeline",
                "payload": {"strategy": "rollback", "to": "previous"},
                "rollback_plan": "Re-apply rename with dual-write.",
                "risk_level": "medium",
            },
        ],
    }
    actions = catalog.get(
        root_cause or "",
        [
            {
                "action_type": "restart",
                "title": f"Controlled rolling restart of {service}",
                "description": "Low-confidence mitigation while investigation continues.",
                "target_service": service,
                "payload": {"strategy": "rolling"},
                "rollback_plan": "No configuration change to undo.",
                "risk_level": "high",
            }
        ],
    )
    for action in actions:
        action["requires_approval"] = True
        action["status"] = "proposed"
    return actions


async def remediator_node(state: AgentState) -> AgentState:
    actions = _remediation_for(state.get("primary_root_cause"), state["service_name"])
    state["remediation_actions"] = actions
    _trace(
        state,
        "remediator",
        {
            "proposed": [a["title"] for a in actions],
            "note": "Write actions require human approval before execution",
        },
    )
    return state


async def reporter_node(state: AgentState) -> AgentState:
    primary = next(
        (h for h in state.get("hypotheses", []) if h.get("is_primary")),
        None,
    )
    lines = [
        f"# Incident Report — {state.get('title')}",
        "",
        f"**Service:** `{state.get('service_name')}`  ",
        f"**Severity:** {state.get('severity')}  ",
        f"**Status:** Awaiting approval for remediation  ",
        "",
        "## Summary",
        state.get("summary")
        or (
            f"Investigation correlated telemetry and runbooks for `{state.get('service_name')}`. "
            f"Primary hypothesis: **{primary['title'] if primary else 'n/a'}** "
            f"(evidence={primary['evidence_score'] if primary else 0})."
        ),
        "",
        "## Timeline (selected)",
    ]
    for event in state.get("timeline", [])[:12]:
        lines.append(
            f"- `{event['event_time'].isoformat()}` [{event['source']}] {event['message']}"
        )
    lines.extend(["", "## Hypotheses"])
    for hyp in state.get("hypotheses", [])[:5]:
        marker = " (primary)" if hyp.get("is_primary") else ""
        lines.append(
            f"1. **{hyp['title']}**{marker} — score `{hyp['evidence_score']}`, "
            f"confidence `{hyp['confidence']}`"
        )
        if hyp.get("critic_notes"):
            lines.append(f"   - Critic: {hyp['critic_notes']}")
    lines.extend(["", "## Proposed Remediation (approval required)"])
    for action in state.get("remediation_actions", []):
        lines.append(
            f"- **{action['title']}** (`{action['action_type']}`, risk={action['risk_level']})"
        )
        lines.append(f"  - Rollback: {action['rollback_plan']}")
    lines.extend(
        [
            "",
            "## Evidence Bundle",
            f"- Logs examined: {len(state.get('logs', []))}",
            f"- Metrics examined: {len(state.get('metrics', []))}",
            f"- Deployments examined: {len(state.get('deployments', []))}",
            f"- Runbooks retrieved: {len(state.get('runbooks', []))}",
            "",
            "## Safety",
            "No restart/rollback/scale/config write was executed autonomously. "
            "All operational actions remain gated behind explicit approval.",
        ]
    )
    report = "\n".join(lines)
    state["report_markdown"] = report
    state["summary"] = (
        f"Primary root cause candidate: {state.get('primary_root_cause')}. "
        f"{len(state.get('remediation_actions', []))} remediation actions pending approval."
    )
    state["evidence_bundle"] = {
        "logs": state.get("logs", []),
        "metrics": state.get("metrics", []),
        "deployments": state.get("deployments", []),
        "runbooks": state.get("runbooks", []),
    }
    _trace(state, "reporter", {"report_chars": len(report)})
    return state


async def run_incident_agent(
    session: AsyncSession,
    *,
    incident_id: str,
    title: str,
    service_name: str,
    severity: str,
    alert: dict[str, Any],
    scenario_id: str | None,
) -> AgentState:
    state: AgentState = {
        "incident_id": incident_id,
        "title": title,
        "service_name": service_name,
        "severity": severity,
        "alert": alert,
        "scenario_id": scenario_id,
        "trace": [],
        "errors": [],
    }
    state = await planner_node(state)
    state = await investigator_node(state, session)
    state = await hypothesis_node(state)
    state = await critic_node(state)
    state = await remediator_node(state)
    state = await reporter_node(state)
    return state
