"""Gather full article text and an image for an event that will be summarised."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import httpx
import trafilatura
from googlenewsdecoder import gnewsdecoder

from get_news.llm import Material
from get_news.models import Article, Cluster
from get_news.textutil import domain_of

log = logging.getLogger(__name__)


def resolve_url(article: Article) -> str | None:
    """Publisher URL for an article; Google News links are decoded on demand only."""
    if not article.gnews:
        return article.url
    try:
        result = gnewsdecoder(article.url, interval=1)
    except Exception as exc:
        log.info("google news decode failed: %s", exc)
        return None
    return result.get("decoded_url") if result.get("status") else None


_MAX_PAGE_BYTES = 3_000_000


def _download_html(http: httpx.Client, url: str) -> str:
    """Fetch an HTML page, refusing other content types and oversized responses."""
    with http.stream("GET", url) as response:
        response.raise_for_status()
        if "html" not in response.headers.get("content-type", "html"):
            raise ValueError(f"not HTML: {response.headers.get('content-type')}")
        body = bytearray()
        for chunk in response.iter_bytes():
            body.extend(chunk)
            if len(body) > _MAX_PAGE_BYTES:
                raise ValueError("page too large")
        return body.decode(response.encoding or "utf-8", errors="replace")


def _extract(http: httpx.Client, url: str, max_chars: int) -> tuple[str, str | None]:
    html = _download_html(http, url)
    text = trafilatura.extract(html, url=url, favor_precision=True, include_comments=False) or ""
    metadata = trafilatura.extract_metadata(html, default_url=url)
    image = metadata.image if metadata and metadata.image and metadata.image.startswith("http") else None
    return text[:max_chars], image


def gather(cluster: Cluster, http: httpx.Client, settings: SimpleNamespace) -> tuple[Material, dict[str, str]]:
    """Full text from up to N readable publishers, plus headlines from the rest.

    Returns the material and article key -> resolved publisher URL for links in the message.
    """
    digest = settings.digest
    skip = set(settings.fulltext_skip_domains)
    texts: list[tuple[str, str, str, str]] = []
    resolved: dict[str, str] = {}
    image: str | None = None
    used_domains: set[str] = set()
    failed_domains: set[str] = set()

    # Direct links first: Google News decoding costs extra requests and can be rate limited.
    for article in sorted(cluster.articles, key=lambda a: a.gnews):
        if len(texts) >= digest.max_fulltext_articles:
            break
        if article.domain in used_domains or article.domain in skip or article.domain in failed_domains:
            continue
        url = resolve_url(article)
        if not url:
            continue
        resolved[article.key] = url
        if domain_of(url) in skip:
            continue
        try:
            text, page_image = _extract(http, url, digest.max_article_chars)
        except Exception as exc:
            log.info("full text failed for %s: %s", url, exc)
            failed_domains.add(article.domain)
            continue
        image = image or page_image
        if len(text) >= 300:
            texts.append((article.source_name, url, article.title, text))
            used_domains.add(article.domain)

    headlines = []
    for article in cluster.articles:
        if article.domain in used_domains:
            continue
        line = f"{article.source_name}: {article.title}"
        headlines.append(f"{line}. {article.snippet}" if article.snippet else line)
    image = image or next((a.image for a in cluster.articles if a.image and a.image.startswith("http")), None)
    return Material(texts=texts, headlines=list(dict.fromkeys(headlines))[:15], image=image), resolved
