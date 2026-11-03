"""Decide whether stories describe the same event, and group articles into event clusters."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from get_news.models import Article, Cluster

# Given the subject's headlines and candidate clusters, return the candidate covering the
# same specific event, or None.
SameEventCheck = Callable[[list[str], list[Cluster]], Cluster | None]


@dataclass
class EventMatcher:
    """Embedding similarity settles clear cases; the model decides the ambiguous middle band."""

    same_event: float
    candidate: float
    max_candidates: int
    confirm: SameEventCheck

    def match(self, vector: np.ndarray, subject: list[str], clusters: list[Cluster]) -> Cluster | None:
        if not clusters:
            return None
        scores = np.stack([c.centroid for c in clusters]) @ vector
        order = np.argsort(-scores)
        if scores[order[0]] >= self.same_event:
            return clusters[order[0]]
        candidates = [clusters[i] for i in order[: self.max_candidates] if scores[i] >= self.candidate]
        return self.confirm(subject, candidates) if candidates else None


def assign(
    articles: list[Article],
    vectors: np.ndarray,
    clusters: list[Cluster],
    matcher: EventMatcher,
    max_articles: int,
    now: datetime,
) -> dict[str, str]:
    """Attach each article to the cluster of its event, or start a new cluster.

    `clusters` is extended in place with new clusters; changed clusters get `touched`.
    Returns article key -> cluster id.
    """
    assignment: dict[str, str] = {}
    for article, vector in zip(articles, vectors, strict=True):
        cluster = matcher.match(vector, [article.embed_text], clusters)
        if cluster is not None:
            cluster.add(article, vector, max_articles, now)
        else:
            cluster = Cluster(
                id=uuid.uuid4().hex[:16],
                centroid=vector.copy(),
                articles=[article],
                count=1,
                created_at=now,
                updated_at=now,
                category_hint=article.category_hint,
                touched=True,
            )
            clusters.append(cluster)
        assignment[article.key] = cluster.id
    return assignment
