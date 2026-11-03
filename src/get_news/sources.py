"""Fetch and parse every configured source into Article objects."""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, tzinfo

import feedparser
import httpx
import lxml.html

from get_news.config import Source
from get_news.models import Article
from get_news.textutil import domain_of, parse_date, strip_html

log = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"
_IMG_SRC = re.compile(r"<img[^>]+src=\"([^\"]+)\"", re.I)
_HREF = re.compile(r"<a[^>]+href=\"([^\"]+)\"", re.I)


def http_client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=20, follow_redirects=True)


def fetch_all(sources: list[Source], http: httpx.Client, tz: tzinfo) -> tuple[list[Article], dict[str, str | None]]:
    """Fetch sources concurrently. Returns articles and, per source id, an error message or None."""

    def run(source: Source) -> tuple[Source, list[Article], str | None]:
        try:
            response = http.get(source.url)
            response.raise_for_status()
            return source, PARSERS[source.kind](source, response.content, tz), None
        except Exception as exc:  # one broken source must not stop the others
            log.warning("source %s failed: %s", source.id, exc)
            return source, [], f"{type(exc).__name__}: {exc}"[:300]

    articles: list[Article] = []
    errors: dict[str, str | None] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for source, items, error in pool.map(run, sources):
            articles.extend(items)
            errors[source.id] = error
            if error is None and not items:
                errors[source.id] = "no items parsed"
    return articles, errors


def _entry_date(entry: feedparser.FeedParserDict, tz: tzinfo) -> datetime:
    # dict.get bypasses feedparser's deprecated updated->published key aliasing.
    parsed = dict.get(entry, "published_parsed") or dict.get(entry, "updated_parsed")
    if parsed:
        return datetime(*parsed[:6], tzinfo=UTC)
    raw = dict.get(entry, "published") or dict.get(entry, "updated")
    return parse_date(raw, tz) or datetime.now(UTC)


def _entry_image(entry: feedparser.FeedParserDict) -> str | None:
    for key in ("media_content", "media_thumbnail"):
        for media in entry.get(key) or []:
            if media.get("url"):
                return media["url"]
    for enclosure in entry.get("enclosures") or []:
        if enclosure.get("type", "").startswith("image/") and enclosure.get("href"):
            return enclosure["href"]
    match = _IMG_SRC.search(entry.get("summary") or "")
    return match.group(1).replace("&amp;", "&") if match else None


def parse_rss(source: Source, content: bytes, tz: tzinfo) -> list[Article]:
    articles = []
    for entry in feedparser.parse(content).entries:
        link, title = entry.get("link"), strip_html(entry.get("title"))
        if not link or not title:
            continue
        summary = entry.get("summary") or ""
        techmeme = domain_of(link) == "techmeme.com"
        if techmeme:
            # Techmeme items link to Techmeme; the first outbound link is the original story.
            original = next((h for h in _HREF.findall(summary) if domain_of(h) != "techmeme.com"), None)
            if not original:
                continue
            link = original.replace("&amp;", "&")
        articles.append(
            Article(
                url=link,
                title=title,
                snippet=strip_html(summary)[:500],
                source_id=source.id,
                source_name=source.name,
                domain=domain_of(link),
                category_hint=source.category,
                published_at=_entry_date(entry, tz),
                image=_entry_image(entry),
                techmeme=techmeme,
            )
        )
    return articles


def parse_google_news(source: Source, content: bytes, tz: tzinfo) -> list[Article]:
    articles = []
    for entry in feedparser.parse(content).entries:
        publisher = entry.get("source") or {}
        if not entry.get("link") or not publisher.get("href"):
            continue
        name = publisher.get("title") or domain_of(publisher["href"])
        title = strip_html(entry.get("title")).removesuffix(f" - {name}")
        articles.append(
            Article(
                url=entry["link"],
                title=title,
                snippet="",
                source_id=source.id,
                source_name=name,
                domain=domain_of(publisher["href"]),
                category_hint=source.category,
                published_at=_entry_date(entry, tz),
                gnews=True,
            )
        )
    return articles


def parse_hn(source: Source, content: bytes, tz: tzinfo) -> list[Article]:
    articles = []
    for hit in json.loads(content)["hits"]:
        url = hit.get("url")
        if not url or not hit.get("title"):
            continue
        articles.append(
            Article(
                url=url,
                title=hit["title"],
                snippet="",
                source_id=source.id,
                source_name=source.name,
                domain=domain_of(url),
                category_hint=source.category,
                published_at=datetime.fromtimestamp(hit["created_at_i"], UTC),
                hn_points=int(hit.get("points") or 0),
            )
        )
    return articles


def parse_github_trending(source: Source, content: bytes, tz: tzinfo) -> list[Article]:
    doc = lxml.html.fromstring(content)
    now = datetime.now(UTC)
    articles = []
    for row in doc.xpath('//article[contains(@class,"Box-row")]'):
        href = next(iter(row.xpath(".//h2//a/@href")), None)
        if not href:
            continue
        repo = href.strip("/")
        description = " ".join(" ".join(row.xpath(".//p//text()")).split())
        stars = " ".join(t.strip() for t in row.xpath('.//span[contains(@class,"float-sm-right")]//text()') if t.strip())
        articles.append(
            Article(
                url=f"https://github.com/{repo}",
                title=f"{repo}: {description}" if description else repo,
                snippet=f"{description} ({stars})".strip(),
                source_id=source.id,
                source_name=source.name,
                domain="github.com",
                category_hint=source.category,
                published_at=now,
            )
        )
    return articles


PARSERS = {
    "rss": parse_rss,
    "google_news": parse_google_news,
    "hn": parse_hn,
    "github_trending": parse_github_trending,
}
