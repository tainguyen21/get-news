from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from get_news.config import load_settings
from get_news.models import Article, Cluster

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 3, 4, 0, tzinfo=UTC)  # 11:00 in Vietnam


@pytest.fixture
def settings():
    return load_settings(ROOT)


def make_article(domain: str = "example.com", minutes_ago: int = 10, **fields) -> Article:
    defaults = dict(
        url=f"https://{domain}/story-{minutes_ago}",
        title=f"Story on {domain}",
        snippet="",
        source_id="test",
        source_name=domain,
        domain=domain,
        category_hint="tech",
        published_at=NOW - timedelta(minutes=minutes_ago),
    )
    defaults.update(fields)
    return Article(**defaults)


def unit(*values: float) -> np.ndarray:
    vector = np.asarray(values, dtype=np.float32)
    return vector / np.linalg.norm(vector)


def make_cluster(cluster_id: str, vector: np.ndarray, articles: list[Article] | None = None, **fields) -> Cluster:
    articles = articles or [make_article()]
    return Cluster(
        id=cluster_id,
        centroid=vector,
        articles=articles,
        count=len(articles),
        created_at=NOW - timedelta(hours=1),
        updated_at=NOW,
        category_hint="tech",
        **fields,
    )
