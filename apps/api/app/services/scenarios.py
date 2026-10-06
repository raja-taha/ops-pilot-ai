"""Synthetic production incident scenarios for demos and evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass
class Scenario:
    id: str
    title: str
    service_name: str
    severity: str
    description: str
    expected_root_cause: str
    dependencies: list[str] = field(default_factory=list)
    alert: dict[str, Any] = field(default_factory=dict)
    logs: list[dict[str, Any]] = field(default_factory=list)
    metrics: list[dict[str, Any]] = field(default_factory=list)
    deployments: list[dict[str, Any]] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ts(minutes_ago: int) -> str:
    return (_now() - timedelta(minutes=minutes_ago)).isoformat()


SCENARIOS: dict[str, Scenario] = {
    "payment-latency-spike": Scenario(
        id="payment-latency-spike",
        title="Payment API p99 latency breach",
        service_name="payment-api",
        severity="critical",
        description="Checkout failures rising after a recent deploy; DB connection pool saturation.",
        expected_root_cause="connection_pool_exhaustion_after_deploy",
        dependencies=["postgres-payments", "redis-cache", "fraud-service"],
        alert={
            "alertname": "HighP99Latency",
            "service": "payment-api",
            "threshold": "800ms",
            "current": "2400ms",
            "environment": "prod",
        },
        deployments=[
            {
                "service": "payment-api",
                "version": "v2.14.0",
                "previous": "v2.13.3",
                "at": _ts(45),
                "change": "Increased checkout concurrency; pool size unchanged",
            }
        ],
        metrics=[
            {"name": "http_request_duration_p99", "value": 2.4, "unit": "s", "at": _ts(5)},
            {"name": "db_pool_active", "value": 100, "unit": "connections", "at": _ts(5)},
            {"name": "db_pool_waiting", "value": 87, "unit": "requests", "at": _ts(5)},
            {"name": "error_rate", "value": 0.18, "unit": "ratio", "at": _ts(5)},
            {"name": "cpu_utilization", "value": 0.42, "unit": "ratio", "at": _ts(5)},
        ],
        logs=[
            {
                "level": "ERROR",
                "at": _ts(8),
                "message": "Timeout acquiring connection from pool after 5000ms",
                "service": "payment-api",
            },
            {
                "level": "WARN",
                "at": _ts(12),
                "message": "Connection pool nearly exhausted (98/100)",
                "service": "payment-api",
            },
            {
                "level": "INFO",
                "at": _ts(45),
                "message": "Deployed payment-api:v2.14.0",
                "service": "deployer",
            },
            {
                "level": "ERROR",
                "at": _ts(6),
                "message": "checkout failed: upstream timeout from payment-api",
                "service": "checkout-bff",
            },
        ],
    ),
    "auth-error-surge": Scenario(
        id="auth-error-surge",
        title="Auth service 401/500 surge",
        service_name="auth-service",
        severity="high",
        description="JWT validation failures after secret rotation mismatch across replicas.",
        expected_root_cause="jwt_secret_rotation_mismatch",
        dependencies=["redis-sessions", "user-db"],
        alert={
            "alertname": "AuthErrorRateHigh",
            "service": "auth-service",
            "error_rate": "0.35",
            "environment": "prod",
        },
        deployments=[
            {
                "service": "auth-service",
                "version": "v1.9.2",
                "previous": "v1.9.1",
                "at": _ts(30),
                "change": "Rotated JWT signing secret via configmap",
            }
        ],
        metrics=[
            {"name": "http_5xx_rate", "value": 0.22, "unit": "ratio", "at": _ts(3)},
            {"name": "http_401_rate", "value": 0.41, "unit": "ratio", "at": _ts(3)},
            {"name": "token_validation_failures", "value": 1200, "unit": "count/min", "at": _ts(3)},
        ],
        logs=[
            {
                "level": "ERROR",
                "at": _ts(4),
                "message": "JWT signature verification failed: kid mismatch",
                "service": "auth-service",
            },
            {
                "level": "WARN",
                "at": _ts(10),
                "message": "Replica auth-service-7f9d still using previous JWT secret",
                "service": "auth-service",
            },
            {
                "level": "INFO",
                "at": _ts(30),
                "message": "Config reload: JWT_SECRET rotated",
                "service": "auth-service",
            },
        ],
    ),
    "orders-oom": Scenario(
        id="orders-oom",
        title="Orders worker OOMKill loop",
        service_name="orders-worker",
        severity="critical",
        description="Memory leak in batch exporter causing repeated OOMKills.",
        expected_root_cause="memory_leak_batch_exporter",
        dependencies=["kafka-orders", "s3-exports"],
        alert={
            "alertname": "PodCrashLooping",
            "service": "orders-worker",
            "reason": "OOMKilled",
            "restarts": 14,
        },
        deployments=[
            {
                "service": "orders-worker",
                "version": "v3.2.1",
                "previous": "v3.2.0",
                "at": _ts(120),
                "change": "Enabled large batch CSV export",
            }
        ],
        metrics=[
            {"name": "container_memory_working_set", "value": 1.95, "unit": "GiB", "at": _ts(2)},
            {"name": "memory_limit", "value": 2.0, "unit": "GiB", "at": _ts(2)},
            {"name": "restart_count", "value": 14, "unit": "count", "at": _ts(2)},
        ],
        logs=[
            {
                "level": "ERROR",
                "at": _ts(2),
                "message": "java.lang.OutOfMemoryError: Java heap space",
                "service": "orders-worker",
            },
            {
                "level": "WARN",
                "at": _ts(15),
                "message": "Export buffer grew to 1.7GiB for batch job export-9921",
                "service": "orders-worker",
            },
        ],
    ),
    "checkout-dependency": Scenario(
        id="checkout-dependency",
        title="Checkout cascading failures from inventory",
        service_name="checkout-bff",
        severity="high",
        description="Inventory service latency causes checkout timeouts; circuit breaker stuck open.",
        expected_root_cause="inventory_latency_circuit_open",
        dependencies=["inventory-service", "payment-api", "cart-service"],
        alert={
            "alertname": "CheckoutSuccessRateLow",
            "service": "checkout-bff",
            "success_rate": "0.61",
        },
        deployments=[],
        metrics=[
            {"name": "checkout_success_rate", "value": 0.61, "unit": "ratio", "at": _ts(4)},
            {
                "name": "inventory_dependency_latency_p95",
                "value": 3.1,
                "unit": "s",
                "at": _ts(4),
            },
            {"name": "circuit_breaker_open", "value": 1, "unit": "bool", "at": _ts(4)},
        ],
        logs=[
            {
                "level": "ERROR",
                "at": _ts(5),
                "message": "CircuitBreaker('inventory-service') OPEN after 50 failures",
                "service": "checkout-bff",
            },
            {
                "level": "ERROR",
                "at": _ts(7),
                "message": "inventory-service timeout after 3000ms",
                "service": "checkout-bff",
            },
            {
                "level": "WARN",
                "at": _ts(20),
                "message": "Slow query on stock_levels (avg 2.8s)",
                "service": "inventory-service",
            },
        ],
    ),
    "search-index-lag": Scenario(
        id="search-index-lag",
        title="Search index lag / stale results",
        service_name="search-indexer",
        severity="medium",
        description="Kafka consumer lag after partition rebalance causes stale product search.",
        expected_root_cause="kafka_consumer_lag_rebalance",
        dependencies=["kafka-catalog", "opensearch"],
        alert={
            "alertname": "SearchIndexLag",
            "service": "search-indexer",
            "lag": "450000",
        },
        deployments=[
            {
                "service": "search-indexer",
                "version": "v1.4.0",
                "previous": "v1.3.8",
                "at": _ts(90),
                "change": "Scaled from 3 to 6 consumers",
            }
        ],
        metrics=[
            {"name": "kafka_consumer_lag", "value": 450000, "unit": "messages", "at": _ts(3)},
            {"name": "index_docs_per_sec", "value": 12, "unit": "rate", "at": _ts(3)},
        ],
        logs=[
            {
                "level": "WARN",
                "at": _ts(6),
                "message": "Rebalance in progress; paused consumption on 4 partitions",
                "service": "search-indexer",
            },
            {
                "level": "ERROR",
                "at": _ts(9),
                "message": "CommitFailedException during rebalance",
                "service": "search-indexer",
            },
        ],
    ),
    "cdn-cache-miss": Scenario(
        id="cdn-cache-miss",
        title="CDN origin overload from cache purge",
        service_name="edge-cdn",
        severity="high",
        description="Mass cache purge caused origin thundering herd.",
        expected_root_cause="cache_purge_thundering_herd",
        dependencies=["origin-web", "image-resizer"],
        alert={
            "alertname": "OriginErrorBudgetBurn",
            "service": "edge-cdn",
            "cache_hit_ratio": "0.22",
        },
        deployments=[],
        metrics=[
            {"name": "cache_hit_ratio", "value": 0.22, "unit": "ratio", "at": _ts(5)},
            {"name": "origin_rps", "value": 18000, "unit": "rps", "at": _ts(5)},
            {"name": "origin_5xx_rate", "value": 0.09, "unit": "ratio", "at": _ts(5)},
        ],
        logs=[
            {
                "level": "INFO",
                "at": _ts(25),
                "message": "Bulk purge completed for path /assets/* (2.1M objects)",
                "service": "edge-cdn",
            },
            {
                "level": "ERROR",
                "at": _ts(8),
                "message": "origin-web: upstream connect error or disconnect/reset",
                "service": "edge-cdn",
            },
        ],
    ),
    "notif-queue-backlog": Scenario(
        id="notif-queue-backlog",
        title="Notification queue backlog",
        service_name="notification-service",
        severity="medium",
        description="SMTP provider rate limiting causes growing Redis queue depth.",
        expected_root_cause="smtp_rate_limit_queue_backlog",
        dependencies=["redis-queues", "smtp-provider"],
        alert={
            "alertname": "QueueDepthHigh",
            "service": "notification-service",
            "depth": "250000",
        },
        deployments=[],
        metrics=[
            {"name": "queue_depth", "value": 250000, "unit": "messages", "at": _ts(2)},
            {"name": "smtp_429_rate", "value": 0.47, "unit": "ratio", "at": _ts(2)},
            {"name": "send_success_rate", "value": 0.51, "unit": "ratio", "at": _ts(2)},
        ],
        logs=[
            {
                "level": "ERROR",
                "at": _ts(3),
                "message": "SMTP 429 Too Many Requests from provider",
                "service": "notification-service",
            },
            {
                "level": "WARN",
                "at": _ts(11),
                "message": "Retrying 8400 messages with exponential backoff",
                "service": "notification-service",
            },
        ],
    ),
    "ml-feature-skew": Scenario(
        id="ml-feature-skew",
        title="Fraud model score collapse",
        service_name="fraud-service",
        severity="high",
        description="Feature pipeline schema drift after catalog change; model scores invalid.",
        expected_root_cause="feature_schema_drift",
        dependencies=["feature-store", "payment-api"],
        alert={
            "alertname": "FraudScoreAnomaly",
            "service": "fraud-service",
            "mean_score": "0.02",
        },
        deployments=[
            {
                "service": "feature-pipeline",
                "version": "v0.8.4",
                "previous": "v0.8.3",
                "at": _ts(60),
                "change": "Renamed merchant_category_code to mcc_code",
            }
        ],
        metrics=[
            {"name": "fraud_score_mean", "value": 0.02, "unit": "score", "at": _ts(4)},
            {"name": "feature_null_rate", "value": 0.88, "unit": "ratio", "at": _ts(4)},
            {"name": "false_negative_proxy", "value": 0.31, "unit": "ratio", "at": _ts(4)},
        ],
        logs=[
            {
                "level": "ERROR",
                "at": _ts(5),
                "message": "Missing feature merchant_category_code; defaulting to 0",
                "service": "fraud-service",
            },
            {
                "level": "WARN",
                "at": _ts(18),
                "message": "Schema validation warning: unexpected field mcc_code",
                "service": "feature-pipeline",
            },
        ],
    ),
}


def list_scenarios() -> list[Scenario]:
    return list(SCENARIOS.values())


def get_scenario(scenario_id: str) -> Scenario | None:
    return SCENARIOS.get(scenario_id)


def resolve_scenario_from_alert(
    service_name: str | None, alert: dict[str, Any], scenario_id: str | None
) -> Scenario:
    if scenario_id and scenario_id in SCENARIOS:
        return SCENARIOS[scenario_id]

    svc = (service_name or alert.get("service") or "").lower()
    for scenario in SCENARIOS.values():
        if scenario.service_name == svc:
            return scenario

    # Fallback synthetic scenario built from free-form alert
    return Scenario(
        id="custom-alert",
        title=alert.get("alertname") or f"Alert on {svc or 'unknown'}",
        service_name=svc or "unknown-service",
        severity=str(alert.get("severity") or "high"),
        description="Custom alert ingested without a predefined scenario.",
        expected_root_cause="insufficient_evidence",
        dependencies=[],
        alert=alert,
        logs=[
            {
                "level": "WARN",
                "at": _ts(5),
                "message": f"Alert received for {svc or 'unknown'}: {alert}",
                "service": svc or "unknown-service",
            }
        ],
        metrics=[
            {"name": "alert_firing", "value": 1, "unit": "bool", "at": _ts(1)},
        ],
        deployments=[],
    )
