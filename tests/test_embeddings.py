import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.services.embeddings import cosine_similarity, evidence_score, local_embed  # noqa: E402


def test_local_embed_stable_and_normalized():
    a = local_embed("connection pool timeout payment-api")
    b = local_embed("connection pool timeout payment-api")
    c = local_embed("jwt secret rotation mismatch")
    assert a == b
    assert abs(sum(x * x for x in a) - 1.0) < 1e-3
    assert cosine_similarity(a, b) > 0.99
    assert cosine_similarity(a, c) < 0.9


def test_evidence_score_rewards_token_hits():
    score = evidence_score(
        ["pool", "connection", "timeout"],
        "Timeout acquiring connection from pool after 5000ms",
    )
    assert score >= 0.9
