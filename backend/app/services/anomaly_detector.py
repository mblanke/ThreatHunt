"""Embedding-based anomaly detection using Roadrunner's bge-m3 model.

Converts dataset rows to embeddings, clusters them, and flags outliers
that deviate significantly from the cluster centroids.  Uses cosine
distance and simple k-means-like centroid computation.
"""

import asyncio
import json
import logging
import math
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import async_session_factory
from app.db.models import AnomalyResult, Dataset, DatasetRow

logger = logging.getLogger(__name__)

EMBED_URL = f"{settings.roadrunner_url}/api/embed"
EMBED_MODEL = "bge-m3"
BATCH_SIZE = 32   # rows per embedding batch
MAX_ROWS = 2000   # cap for anomaly detection

# --- math helpers (no numpy required) ---

def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _cosine_distance(a: list[float], b: list[float]) -> float:
    na, nb = _norm(a), _norm(b)
    if na == 0 or nb == 0:
        return 1.0
    return 1.0 - _dot(a, b) / (na * nb)


def _mean_vector(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    dim = len(vectors[0])
    n = len(vectors)
    return [sum(v[i] for v in vectors) / n for i in range(dim)]


def _row_to_text(data: dict) -> str:
    """Flatten a row dict to a single string for embedding."""
    parts = []
    for k, v in data.items():
        sv = str(v).strip()
        if sv and sv.lower() not in ('none', 'null', ''):
            parts.append(f"{k}={sv}")
    return " | ".join(parts)[:2000]  # cap length


async def _embed_batch(texts: list[str], client: httpx.AsyncClient) -> list[list[float]]:
    """Get embeddings from Roadrunner's Ollama API."""
    resp = await client.post(
        EMBED_URL,
        json={"model": EMBED_MODEL, "input": texts},
        timeout=120.0,
    )
    resp.raise_for_status()
    data = resp.json()
    # Ollama returns {"embeddings": [[...], ...]}
    return data.get("embeddings", [])


def _simple_cluster(
    embeddings: list[list[float]],
    k: int = 3,
    max_iter: int = 20,
) -> tuple[list[int], list[list[float]]]:
    """Simple k-means clustering (no numpy dependency).

    Returns (assignments, centroids).
    """
    n = len(embeddings)
    if n <= k:
        return list(range(n)), embeddings[:]

    # Init centroids: evenly spaced indices
    step = max(n // k, 1)
    centroids = [embeddings[i * step % n] for i in range(k)]
    assignments = [0] * n

    for _ in range(max_iter):
        # Assign to nearest centroid
        new_assignments = []
        for emb in embeddings:
            dists = [_cosine_distance(emb, c) for c in centroids]
            new_assignments.append(dists.index(min(dists)))

        if new_assignments == assignments:
            break
        assignments = new_assignments

        # Recompute centroids
        for ci in range(k):
            members = [embeddings[j] for j in range(n) if assignments[j] == ci]
            if members:
                centroids[ci] = _mean_vector(members)

    return assignments, centroids


async def detect_anomalies(
    dataset_id: str,
    k: int = 3,
    outlier_threshold: float = 0.35,
) -> list[dict]:
    """Run embedding-based anomaly detection on a dataset.

    1. Load rows    2. Embed via bge-m3    3. Cluster    4. Flag outliers.
    """
    async with async_session_factory() as db:
        # Load rows
        result = await db.execute(
            select(DatasetRow.id, DatasetRow.row_index, DatasetRow.data)
            .where(DatasetRow.dataset_id == dataset_id)
            .order_by(DatasetRow.row_index)
            .limit(MAX_ROWS)
        )
        rows = result.all()
        if not rows:
            logger.info("No rows for anomaly detection in dataset %s", dataset_id)
            return []

        row_ids = [r[0] for r in rows]
        row_indices = [r[1] for r in rows]
        texts = [_row_to_text(r[2]) for r in rows]

        logger.info("Anomaly detection: %d rows, embedding with %s", len(texts), EMBED_MODEL)

        # Embed in batches
        all_embeddings: list[list[float]] = []
        async with httpx.AsyncClient() as client:
            for i in range(0, len(texts), BATCH_SIZE):
                batch = texts[i : i + BATCH_SIZE]
                try:
                    embs = await _embed_batch(batch, client)
                    all_embeddings.extend(embs)
                except Exception as e:
                    logger.error("Embedding batch %d failed: %s", i, e)
                    # Fill with zeros so indices stay aligned
                    all_embeddings.extend([[0.0] * 1024] * len(batch))

        if not all_embeddings or len(all_embeddings) != len(texts):
            logger.error("Embedding count mismatch")
            return []

        # Cluster
        actual_k = min(k, len(all_embeddings))
        assignments, centroids = _simple_cluster(all_embeddings, k=actual_k)

        # Compute distances from centroid
        anomalies: list[dict] = []
        for idx, (emb, cluster_id) in enumerate(zip(all_embeddings, assignments)):
            dist = _cosine_distance(emb, centroids[cluster_id])
            is_outlier = dist > outlier_threshold
            anomalies.append({
                "row_id": row_ids[idx],
                "row_index": row_indices[idx],
                "anomaly_score": round(dist, 4),
                "distance_from_centroid": round(dist, 4),
                "cluster_id": cluster_id,
                "is_outlier": is_outlier,
            })

        # Save to DB
        outlier_count = 0
        for a in anomalies:
            ar = AnomalyResult(
                dataset_id=dataset_id,
                row_id=a["row_id"],
                anomaly_score=a["anomaly_score"],
                distance_from_centroid=a["distance_from_centroid"],
                cluster_id=a["cluster_id"],
                is_outlier=a["is_outlier"],
            )
            db.add(ar)
            if a["is_outlier"]:
                outlier_count += 1

        await db.commit()
        logger.info(
            "Anomaly detection complete: %d rows, %d outliers (threshold=%.2f)",
            len(anomalies), outlier_count, outlier_threshold,
        )

        return sorted(anomalies, key=lambda x: x["anomaly_score"], reverse=True)