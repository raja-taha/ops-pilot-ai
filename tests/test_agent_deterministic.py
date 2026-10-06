import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.agents.workflow import (  # noqa: E402
    _build_hypotheses_deterministic,
    critic_node,
    remediator_node,
)
from app.agents.state import AgentState  # noqa: E402
from app.services.scenarios import SCENARIOS  # noqa: E402


@pytest.mark.asyncio
async def test_payment_latency_primary_hypothesis():
    scenario = SCENARIOS["payment-latency-spike"]
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
            {
                "title": "Payment API — Connection Pool Saturation",
                "content": "connection_pool_exhaustion_after_deploy pool timeout",
            }
        ],
        "trace": [],
    }
    hyps = _build_hypotheses_deterministic(state)
    state["hypotheses"] = hyps
    state = await critic_node(state)
    assert state["primary_root_cause"] == scenario.expected_root_cause
    assert state["hypotheses"][0]["evidence_score"] >= 0.55


@pytest.mark.asyncio
async def test_remediation_requires_approval_flag():
    state: AgentState = {
        "service_name": "payment-api",
        "primary_root_cause": "connection_pool_exhaustion_after_deploy",
        "trace": [],
    }
    state = await remediator_node(state)
    assert state["remediation_actions"]
    assert all(a["requires_approval"] is True for a in state["remediation_actions"])


@pytest.mark.parametrize("scenario_id", list(SCENARIOS.keys()))
def test_every_scenario_has_expected_root_cause(scenario_id):
    scenario = SCENARIOS[scenario_id]
    assert scenario.expected_root_cause
    assert scenario.logs
    assert scenario.metrics
