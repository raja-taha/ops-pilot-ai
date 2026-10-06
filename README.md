# OpsPilot

**AI SRE Incident Commander** — turns noisy logs, metrics, and deploys into an evidence-backed incident narrative, then waits for human approval before any remediation.

> **Proof:** This agent can diagnose a synthetic production incident using telemetry and **cannot** execute remediation without approval.

---

## Demo

![OpsPilot console](docs/screenshots/console.svg)

| Screen | What it proves |
|---|---|
| Incident workspace | Correlated timeline + ranked hypotheses with evidence scores |
| Approval gate | Write actions stay `proposed` until an engineer decides |
| Agent trace | Planner → investigator → critic → remediator steps are auditable |
| Report export | Post-incident markdown summary generated from the same evidence bundle |

> Add real PNG/GIF captures under `docs/screenshots/` after your first local run (`console.png`, `approval.gif`, `agent-trace.png`).

---

## Architecture

```text
Next.js incident console
        │
        ▼
FastAPI orchestration API
        │
        ▼
Agent workflow (planner → investigator → critic → remediator → reporter)
        │
        ├── Telemetry tools (synthetic / Prometheus+Loki)
        ├── Runbook RAG (PostgreSQL + pgvector)
        ├── Redis short-lived incident state
        └── OpenTelemetry traces
```

Full write-up: [`docs/architecture.md`](docs/architecture.md)

---

## Hard engineering problems

1. **Tool permissions** — diagnosis is autonomous; restart/rollback/scale/config are never exposed as free agent tools. Execution only happens after `POST .../decision` with `approved=true`.
2. **Cross-source correlation** — deploys, logs, and metrics are normalized onto one timeline before hypothesis ranking.
3. **Anti-hallucination critic** — hypotheses below `EVIDENCE_SCORE_THRESHOLD`, or with sparse supporting artifacts, are demoted even if the model is confident.
4. **Replayable evals** — eight synthetic scenarios with expected root causes power regression checks in CI.

---

## Evaluation

| Metric | Dataset | Current result |
|---|---|---|
| Root-cause Top-1 accuracy | 8 synthetic incidents (`evals/scenarios.json`) | **100% (8/8)**, ~2ms avg latency |

```bash
python evals/run_eval.py
# writes evals/latest_results.json
```

---

## Safety & reliability

- API key auth on all mutating/read workspace routes (`X-API-Key`)
- Remediation actions default to `requires_approval=true`
- Executor is **synthetic** — no real Kubernetes/cloud mutations
- Complete audit trail (`audit_logs`) for create / investigate / approve / reject / execute
- Agent traces persisted on the incident + mirrored in Redis
- OpenAI optional — offline mock agent keeps demos and CI green
- Known limitation: production Prometheus/Loki adapters are thin; synthetic mode is the supported happy path

---

## Run locally

### Prerequisites

- Docker + Docker Compose (at least for Postgres + Redis)
- Python 3.12+ with a `venv` inside `apps/api` for local API work
- Node 20+ for the Next.js console
- (Optional) `OPENAI_API_KEY` for live LLM mode

### 1. Configure environment

```bash
cp .env.example .env
# fill in secrets — at minimum set API_KEY (and matching NEXT_PUBLIC_API_KEY)
```

### 2. Start the stack

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Web console | http://localhost:3000 |
| API + OpenAPI docs | http://localhost:8000/docs |
| Postgres | `localhost:5432` |
| Redis | `localhost:6379` |

### 3. Run a demo incident

1. Open the console → pick **Payment API p99 latency breach**
2. Click **Run incident agent**
3. Review timeline, hypotheses, critic notes
4. **Approve** or **Reject** a remediation action
5. Export the markdown incident report

CLI alternative:

```bash
python scripts/seed_demo.py payment-latency-spike
```

### Without Docker (API + local venv)

Windows PowerShell:

```powershell
# terminal 1 — infra (from repo root)
docker compose up db redis

# terminal 2 — API
cd apps\api
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python -m app.db.seed
uvicorn app.main:app --reload --port 8000

# terminal 3 — web (from repo root)
cd apps\web
npm install
npm run dev
```

Re-activate later from `apps\api` with `.\venv\Scripts\activate`.  
macOS/Linux: `source venv/bin/activate`.

---

## API examples

Create + investigate:

```bash
curl -s -X POST http://localhost:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me-to-a-strong-secret" \
  -d '{"scenario_id":"payment-latency-spike","auto_investigate":true}'
```

Approve a remediation action:

```bash
curl -s -X POST http://localhost:8000/api/v1/incidents/{incident_id}/actions/{action_id}/decision \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me-to-a-strong-secret" \
  -d '{"approved":true,"decided_by":"oncall-engineer","notes":"Evidence looks solid"}'
```

Postman collection: [`postman/OpsPilot.postman_collection.json`](postman/OpsPilot.postman_collection.json)

---

## Repository layout

```text
ops-pilot-ai/
├── apps/api/           # FastAPI + agent workflow
├── apps/web/           # Next.js incident console
├── services/worker/    # Redis heartbeat worker
├── evals/              # Root-cause benchmark
├── tests/              # Unit tests
├── scripts/            # Demo helpers
├── postman/            # API collection
├── docs/               # Architecture + screenshots
├── docker-compose.yml
└── .env.example
```

---

## Tradeoffs

- **Synthetic telemetry first** — reliable demos/evals over fragile local Prom/Loki wiring.
- **Deterministic mock agent by default** — portfolio proof stays reproducible without paid tokens; set `OPENAI_API_KEY` + `AGENT_MODE=openai` for live LLM ranking.
- **No real cluster control plane** — approval gate is the product signal; execution is intentionally sandboxed.
- **Simple API-key auth** — enough for a private demo; not a multi-tenant SSO product.

---

## Roadmap

- [ ] Kubernetes tool adapters behind the same approval gate
- [ ] Deployment diffing across releases
- [ ] Slack/Teams incident bridge
- [ ] Automated postmortem generator with blameless template
- [ ] Expand eval set to 30+ replayable incidents

---

## Tech stack

Python · FastAPI · LangGraph-style agent graph · OpenAI (optional) · PostgreSQL · pgvector · Redis · OpenTelemetry · Next.js · Docker

---

Built as **Day 1** of the Advanced AI Portfolio Challenge — Agentic AI + Observability + Human-in-the-loop.
