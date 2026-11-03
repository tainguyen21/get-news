"""Parsers against real feed samples saved on 2026-11-03."""

from zoneinfo import ZoneInfo

from conftest import FIXTURES

from get_news.config import Source
from get_news.sources import parse_github_trending, parse_google_news, parse_hn, parse_rss

VN = ZoneInfo("Asia/Ho_Chi_Minh")


def source(kind="rss", name="Test", category="world"):
    return Source(id=f"{kind}-test", kind=kind, name=name, category=category, url="https://example.com")


def load(name):
    return (FIXTURES / name).read_bytes()


def test_rss_bbc_has_dates_snippets_and_images():
    articles = parse_rss(source(name="BBC"), load("bbc-world.xml"), VN)
    assert len(articles) > 20
    first = articles[0]
    assert first.domain == "bbc.co.uk"
    assert first.snippet and first.image.startswith("https://")
    assert first.published_at.tzinfo is not None


def test_rss_techmeme_uses_original_article_link():
    articles = parse_rss(source(name="Techmeme", category="tech"), load("techmeme.xml"), VN)
    assert articles
    assert all(a.techmeme for a in articles)
    assert all(a.domain != "techmeme.com" for a in articles)
    assert articles[0].url.startswith("https://www.theinformation.com/")


def test_rss_vietnamese_feeds_parse_nonstandard_dates():
    tuoitre = parse_rss(source(name="Tuổi Trẻ"), load("tuoitre-world.xml"), VN)
    genk = parse_rss(source(name="Genk", category="tech"), load("genk-ai.xml"), VN)
    vnexpress = parse_rss(source(name="VnExpress"), load("vnexpress-thoi-su.xml"), VN)
    for articles in (tuoitre, genk, vnexpress):
        assert len(articles) > 20
        assert all(a.published_at.year == 2026 for a in articles)
        assert any(a.image for a in articles)
    # "11/3/2026 9:48:00 AM" in Vietnam is 02:48 UTC.
    assert tuoitre[0].published_at.hour == 2 and tuoitre[0].published_at.minute == 48


def test_google_news_takes_publisher_from_source_element():
    articles = parse_google_news(source(kind="google_news", name="Google News"), load("gnews-world.xml"), VN)
    assert len(articles) > 20
    first = articles[0]
    assert first.gnews and first.domain == "pbs.org" and first.source_name == "PBS"
    assert not first.title.endswith(" - PBS")


def test_hacker_news_points():
    articles = parse_hn(source(kind="hn", name="Hacker News", category="tech"), load("hn-front-page.json"), VN)
    assert len(articles) > 20
    assert articles[0].hn_points == 2133
    assert articles[0].domain == "rikiyat.github.io"  # github.io user sites are separate publishers


def test_github_trending():
    articles = parse_github_trending(source(kind="github_trending", category="tech"), load("github-trending.html"), VN)
    assert len(articles) == 15
    assert articles[0].url == "https://github.com/vercel-labs/agent-desktop"
    assert "stars today" in articles[0].snippet
