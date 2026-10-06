# OpsPilot Architecture

## Proof statement

> This agent can diagnose a synthetic production incident using telemetry and cannot execute remediation without approval.

## Request / data flow

```text
┌────────────────────┐
│  Next.js Console   │  Launch scenario / approve actions / export report
└─────────┬──────────┘
          │ REST + X-API-Key
┌─────────▼──────────┐
│   FastAPI API      │  Incident orchestration, approval gate, audit log
└─────────┬──────────┘
          │
┌─────────▼──────────────────────────────────────────────┐
│ LangGraph-style agent workflow                         │
│ planner → investigator → hypothesis → critic →         │
│ remediator → reporter                                  │
└─────┬───────────────┬──────────────────┬───────────────┘
      │               │                  │
┌─────▼─────┐  ┌──────▼──────┐   ┌───────▼────────┐
│ Telemetry │  │ Runbook RAG │   │ Redis incident │
│ (synth /  │  │ Postgres +  │   │ short-lived    │
│ Prom/Loki)│  │ pgvector    │   │ state + traces │
└───────────┘  └─────────────┘   └────────────────┘
```

## Permission model

| Capability | Autonomous? | Notes |
|---|---|---|
| Query logs / metrics / deploys | Yes | Read-only tools |
| Retrieve runbooks | Yes | Vector + lexical retrieval |
| Rank hypotheses | Yes | Critic enforces evidence threshold |
| Restart / rollback / scale / config | **No** | Requires explicit approval API call |
| Execute approved action | After approval | Synthetic executor (no real cluster writes) |

## Evidence scoring

1. Investigator gathers timeline artifacts.
2. Hypothesis ranker scores claims against logs/metrics/deploys/runbooks.
3. Critic penalizes high confidence with sparse support and demotes scores below `EVIDENCE_SCORE_THRESHOLD`.
4. Remediator only proposes actions — never executes them.

## Persistence

- **PostgreSQL + pgvector** — incidents, hypotheses, actions, timeline, audit logs, runbook embeddings
- **Redis** — short-lived incident state and agent trace steps
- **OpenTelemetry** — FastAPI spans (console + optional OTLP)

## Failure modes

- Missing OpenAI key → deterministic mock agent (still fully functional)
- Prometheus/Loki unreachable → synthetic telemetry fallback
- Low evidence → provisional primary hypothesis + cautious remediation proposal
