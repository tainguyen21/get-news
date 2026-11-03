"""Digest candidate ordering and per-section selection."""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import datetime

from get_news.clustering import EventMatcher
from get_news.models import Cluster


def prerank(cluster: Cluster, now: datetime) -> float:
    """Cheap signal used to choose which clusters are worth a scoring call."""
    newest = max(a.published_at for a in cluster.articles)
    age_hours = max((now - newest).total_seconds() / 3600, 0)
    return (
        2.0 * math.log1p(len(cluster.publishers()))
        + (1.0 if cluster.techmeme else 0.0)
        + min(cluster.hn_points / 300, 2.0)
        + max(0.0, 1.0 - age_hours / 12)
    )


def is_repeat(cluster: Cluster, others: list[Cluster], matcher: EventMatcher) -> bool:
    """True when another cluster already covers the same event."""
    others = [other for other in others if other.id != cluster.id]
    return matcher.match(cluster.centroid, cluster.headlines(), others) is not None


def digest_order(clusters: list[Cluster], now: datetime) -> list[Cluster]:
    """Overnight hot items first, then by model importance, then by the cheap signal."""
    return sorted(clusters, key=lambda c: (not c.hot_pending, -(c.importance or 0), -prerank(c, now)))


def select(
    ordered: list[Cluster],
    quotas: dict[str, int],
    accept: Callable[[Cluster], bool],
    matcher: EventMatcher,
    already_sent: list[Cluster] = (),
) -> list[Cluster]:
    """Fill each section's quota in order; spare slots go to the other section.

    `accept` performs the expensive material check and is called at most once per cluster.
    Clusters covering the same event as a chosen or recently sent one are skipped; this check
    runs only for clusters reached in order, which keeps model calls few.
    """
    total = sum(quotas.values())
    chosen: list[Cluster] = []
    rejected: set[str] = set()

    def run(per_section_cap: bool) -> None:
        counts = {section: sum(c.category == section for c in chosen) for section in quotas}
        for cluster in ordered:
            if len(chosen) >= total:
                return
            if cluster.category not in quotas or cluster.id in rejected or any(c.id == cluster.id for c in chosen):
                continue
            if per_section_cap and counts[cluster.category] >= quotas[cluster.category]:
                continue
            if is_repeat(cluster, [*already_sent, *chosen], matcher) or not accept(cluster):
                rejected.add(cluster.id)
                continue
            chosen.append(cluster)
            counts[cluster.category] += 1

    run(per_section_cap=True)
    run(per_section_cap=False)
    return chosen
