"""Deterministic local embeddings + optional OpenAI embeddings."""

from __future__ import annotations

import hashlib
import math
import re

import numpy as np

from app.core.config import get_settings

DIM = 384


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def local_embed(text: str, dim: int = DIM) -> list[float]:
    """Hashing trick embedding — works offline and is stable for demos/evals."""
    vec = np.zeros(dim, dtype=np.float64)
    tokens = _tokenize(text)
    if not tokens:
        return vec.tolist()

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.astype(np.float32).tolist()


async def embed_text(text: str) -> list[float]:
    settings = get_settings()
    if settings.use_openai:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.openai_api_key)
            response = await client.embeddings.create(
                model=settings.embedding_model,
                input=text,
            )
            raw = response.data[0].embedding
            # Project to DIM for pgvector column consistency
            arr = np.array(raw, dtype=np.float64)
            if arr.shape[0] == DIM:
                return arr.tolist()
            # simple average pool / pad
            if arr.shape[0] > DIM:
                groups = np.array_split(arr, DIM)
                projected = np.array([g.mean() for g in groups], dtype=np.float64)
            else:
                projected = np.zeros(DIM, dtype=np.float64)
                projected[: arr.shape[0]] = arr
            norm = np.linalg.norm(projected)
            if norm > 0:
                projected = projected / norm
            return projected.astype(np.float32).tolist()
        except Exception:
            return local_embed(text)
    return local_embed(text)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float64)
    vb = np.array(b, dtype=np.float64)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def evidence_score(claim_tokens: list[str], evidence_text: str) -> float:
    if not claim_tokens:
        return 0.0
    blob = evidence_text.lower()
    hits = sum(1 for t in claim_tokens if t.lower() in blob)
    return min(1.0, hits / max(3, len(claim_tokens)))


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def shannon_confidence(scores: list[float]) -> float:
    if not scores:
        return 0.0
    total = sum(max(0.0, s) for s in scores) or 1.0
    probs = [max(1e-9, s) / total for s in scores]
    entropy = -sum(p * math.log(p, 2) for p in probs)
    max_entropy = math.log(len(probs), 2) if len(probs) > 1 else 1.0
    return clamp01(1.0 - (entropy / max_entropy))
