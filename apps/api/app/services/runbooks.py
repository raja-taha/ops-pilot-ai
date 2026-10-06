from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.runbook import RunbookChunk
from app.services.embeddings import cosine_similarity, embed_text, local_embed

RUNBOOK_CORPUS: list[dict] = [
    {
        "service_name": "payment-api",
        "title": "Payment API — Connection Pool Saturation",
        "section": "diagnosis",
        "tags": ["latency", "database", "pool"],
        "content": (
            "Symptoms: rising p99 latency, Timeout acquiring connection from pool, "
            "db_pool_waiting > 0. Check recent deploys that increased concurrency. "
            "Compare pool size vs active connections. Primary root cause is often "
            "connection_pool_exhaustion_after_deploy."
        ),
    },
    {
        "service_name": "payment-api",
        "title": "Payment API — Remediation",
        "section": "remediation",
        "tags": ["scale", "rollback", "pool"],
        "content": (
            "Safe remediation: 1) Rollback to previous version if deploy correlated. "
            "2) Temporarily increase DB pool size and max connections. "
            "3) Scale payment-api replicas only after pool headroom exists. "
            "Always require approval for restart/rollback/scale."
        ),
    },
    {
        "service_name": "auth-service",
        "title": "Auth — JWT Secret Rotation",
        "section": "diagnosis",
        "tags": ["jwt", "401", "rotation"],
        "content": (
            "Symptoms: JWT signature verification failed, kid mismatch, mixed secrets "
            "across replicas after rotation. Expected root cause: jwt_secret_rotation_mismatch. "
            "Verify all pods loaded the new secret and dual-key validation window."
        ),
    },
    {
        "service_name": "auth-service",
        "title": "Auth — Remediation",
        "section": "remediation",
        "tags": ["config", "restart"],
        "content": (
            "Remediation: enable dual-key verification, rolling restart of lagging replicas, "
            "or rollback configmap. Avoid hard cutover without canary."
        ),
    },
    {
        "service_name": "orders-worker",
        "title": "Orders Worker — OOM",
        "section": "diagnosis",
        "tags": ["oom", "memory"],
        "content": (
            "OOMKilled with heap growth after large batch export indicates "
            "memory_leak_batch_exporter. Check export buffer size and restart loops."
        ),
    },
    {
        "service_name": "orders-worker",
        "title": "Orders Worker — Remediation",
        "section": "remediation",
        "tags": ["rollback", "feature_flag"],
        "content": (
            "Disable large batch export feature flag, rollback worker version, "
            "increase memory only as temporary mitigation."
        ),
    },
    {
        "service_name": "checkout-bff",
        "title": "Checkout — Dependency Latency",
        "section": "diagnosis",
        "tags": ["circuit_breaker", "inventory"],
        "content": (
            "Circuit breaker OPEN on inventory-service with high dependency latency "
            "points to inventory_latency_circuit_open. Inspect inventory slow queries."
        ),
    },
    {
        "service_name": "checkout-bff",
        "title": "Checkout — Remediation",
        "section": "remediation",
        "tags": ["drain", "scale"],
        "content": (
            "Mitigate by serving degraded checkout, scale inventory read replicas, "
            "reset circuit after dependency recovery. Prefer inventory fix over BFF restart."
        ),
    },
    {
        "service_name": "search-indexer",
        "title": "Search Indexer — Kafka Lag",
        "section": "diagnosis",
        "tags": ["kafka", "lag", "rebalance"],
        "content": (
            "CommitFailedException and rebalance storms indicate kafka_consumer_lag_rebalance. "
            "Check consumer group stability after scaling."
        ),
    },
    {
        "service_name": "edge-cdn",
        "title": "CDN — Cache Purge Storm",
        "section": "diagnosis",
        "tags": ["cdn", "purge", "origin"],
        "content": (
            "Bulk purge with collapsing cache hit ratio and origin 5xx suggests "
            "cache_purge_thundering_herd. Soft-revalidate and stagger repopulation."
        ),
    },
    {
        "service_name": "notification-service",
        "title": "Notifications — SMTP Rate Limit",
        "section": "diagnosis",
        "tags": ["smtp", "queue"],
        "content": (
            "SMTP 429 with growing queue depth indicates smtp_rate_limit_queue_backlog. "
            "Backoff, shard providers, or shed non-critical emails."
        ),
    },
    {
        "service_name": "fraud-service",
        "title": "Fraud — Feature Skew",
        "section": "diagnosis",
        "tags": ["ml", "features", "schema"],
        "content": (
            "Missing feature merchant_category_code after rename to mcc_code is classic "
            "feature_schema_drift. Block scoring or fall back to rules until pipeline fixed."
        ),
    },
]


async def ensure_runbooks_seeded(session: AsyncSession) -> int:
    result = await session.execute(select(RunbookChunk).limit(1))
    if result.scalar_one_or_none():
        return 0

    count = 0
    for item in RUNBOOK_CORPUS:
        emb = local_embed(f"{item['title']}\n{item['content']}")
        session.add(
            RunbookChunk(
                service_name=item["service_name"],
                title=item["title"],
                section=item["section"],
                content=item["content"],
                tags=item["tags"],
                embedding=emb,
            )
        )
        count += 1
    await session.flush()
    return count


async def retrieve_runbooks(
    session: AsyncSession,
    query: str,
    service_name: str | None = None,
    top_k: int = 4,
) -> list[dict]:
    query_vec = await embed_text(query)

    # Prefer pgvector distance when available; fall back to Python cosine.
    try:
        sql = text(
            """
            SELECT id, service_name, title, section, content, tags,
                   1 - (embedding <=> :emb) AS score
            FROM runbook_chunks
            WHERE (:service IS NULL OR service_name = :service)
            ORDER BY embedding <=> :emb
            LIMIT :k
            """
        )
        rows = (
            await session.execute(
                sql,
                {
                    "emb": str(query_vec),
                    "service": service_name,
                    "k": top_k,
                },
            )
        ).mappings().all()
        if rows:
            return [dict(r) for r in rows]
    except Exception:
        pass

    result = await session.execute(select(RunbookChunk))
    chunks = list(result.scalars().all())
    ranked: list[tuple[float, RunbookChunk]] = []
    for chunk in chunks:
        if service_name and chunk.service_name != service_name:
            # keep some cross-service context but downrank
            service_boost = 0.0
        else:
            service_boost = 0.15
        base = cosine_similarity(query_vec, chunk.embedding or local_embed(chunk.content))
        ranked.append((base + service_boost, chunk))
    ranked.sort(key=lambda x: x[0], reverse=True)
    out = []
    for score, chunk in ranked[:top_k]:
        out.append(
            {
                "id": str(chunk.id),
                "service_name": chunk.service_name,
                "title": chunk.title,
                "section": chunk.section,
                "content": chunk.content,
                "tags": chunk.tags,
                "score": score,
            }
        )
    return out
