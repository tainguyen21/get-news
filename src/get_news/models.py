"""Articles and event clusters, plus their Firestore document shapes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

import numpy as np

from get_news.textutil import url_key


@dataclass
class Article:
    url: str
    title: str
    snippet: str
    source_id: str
    source_name: str
    domain: str
    category_hint: str
    published_at: datetime
    image: str | None = None
    hn_points: int | None = None
    techmeme: bool = False
    gnews: bool = False

    @property
    def key(self) -> str:
        return url_key(self.url)

    @property
    def embed_text(self) -> str:
        return f"{self.title}\n{self.snippet}"[:1000]

    def to_doc(self) -> dict:
        return asdict(self)

    @classmethod
    def from_doc(cls, doc: dict) -> Article:
        return cls(**doc)


@dataclass(eq=False)  # identity equality; centroids are numpy arrays
class Cluster:
    id: str
    centroid: np.ndarray
    articles: list[Article]
    count: int
    created_at: datetime
    updated_at: datetime
    category_hint: str
    # Scoring and delivery state, written by the hot-news and digest steps.
    importance: int | None = None
    category: str | None = None
    scored_publishers: int = 0
    hot_sent_at: datetime | None = None
    hot_pending: bool = False
    digest_sent_at: datetime | None = None
    touched: bool = False

    @property
    def title(self) -> str:
        return self.articles[0].title

    def headlines(self, limit: int = 3) -> list[str]:
        """Distinct headlines (with snippet) describing the event, for model prompts."""
        lines: dict[str, str] = {}
        for article in self.articles:
            if article.title not in lines and len(lines) < limit:
                lines[article.title] = f"{article.title}. {article.snippet[:150]}".rstrip(". ")
        return list(lines.values())

    def publishers(self, since: datetime | None = None) -> set[str]:
        return {a.domain for a in self.articles if since is None or a.published_at >= since}

    @property
    def techmeme(self) -> bool:
        return any(a.techmeme for a in self.articles)

    @property
    def hn_points(self) -> int:
        return max((a.hn_points or 0 for a in self.articles), default=0)

    @property
    def sent(self) -> bool:
        return self.hot_sent_at is not None or self.digest_sent_at is not None

    def add(self, article: Article, vector: np.ndarray, max_articles: int, now: datetime) -> None:
        """Join an article; the centroid is the running mean of member vectors."""
        merged = self.centroid * self.count + vector
        self.centroid = merged / np.linalg.norm(merged)
        self.count += 1
        if len(self.articles) < max_articles:
            self.articles.append(article)
        self.updated_at = now
        self.touched = True

    def content_doc(self, retention: timedelta) -> dict:
        """Fields owned by the ingest job; merged so delivery fields are never overwritten."""
        return {
            "centroid": self.centroid.astype(float).tolist(),
            "articles": [a.to_doc() for a in self.articles],
            "count": self.count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "category_hint": self.category_hint,
            "title": self.title,
            "publishers": sorted(self.publishers()),
            "expire_at": self.updated_at + retention,
        }

    @classmethod
    def from_doc(cls, doc_id: str, doc: dict) -> Cluster:
        return cls(
            id=doc_id,
            centroid=np.asarray(doc["centroid"], dtype=np.float32),
            articles=[Article.from_doc(a) for a in doc["articles"]],
            count=doc["count"],
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
            category_hint=doc.get("category_hint", "world"),
            importance=doc.get("importance"),
            category=doc.get("category"),
            scored_publishers=doc.get("scored_publishers", 0),
            hot_sent_at=doc.get("hot_sent_at"),
            hot_pending=doc.get("hot_pending", False),
            digest_sent_at=doc.get("digest_sent_at"),
        )
