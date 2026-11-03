from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from get_news.textutil import canonical_url, domain_of, parse_date, redact, strip_html, url_key

VN = ZoneInfo("Asia/Ho_Chi_Minh")


def test_url_key_ignores_tracking_scheme_and_www():
    a = "https://www.bbc.co.uk/news/articles/x1?at_medium=RSS&at_campaign=rss#top"
    b = "http://bbc.co.uk/news/articles/x1/"
    assert url_key(a) == url_key(b)
    assert canonical_url(a) == "https://bbc.co.uk/news/articles/x1"


def test_url_key_keeps_meaningful_query():
    assert url_key("https://site.com/item?id=1") != url_key("https://site.com/item?id=2")


def test_domain_of_uses_registered_domain():
    assert domain_of("https://edition.cnn.com/2026/x") == "cnn.com"
    assert domain_of("https://www.bbc.co.uk/news") == "bbc.co.uk"


def test_parse_date_tuoi_tre_without_zone_assumes_vietnam():
    parsed = parse_date("11/3/2026 9:48:00 AM", VN)
    assert parsed == datetime(2026, 11, 3, 2, 48, tzinfo=UTC)


def test_parse_date_genk_short_offset():
    assert parse_date("Mon, 02 Nov 2026 08:59:00 +07", VN) == datetime(2026, 11, 2, 1, 59, tzinfo=UTC)


def test_parse_date_rfc822_and_iso():
    assert parse_date("Tue, 03 Nov 2026 03:39:08 GMT", VN) == datetime(2026, 11, 3, 3, 39, 8, tzinfo=UTC)
    assert parse_date("2026-11-02T22:25:00-05:00", VN) == datetime(2026, 11, 3, 3, 25, tzinfo=UTC)
    assert parse_date("not a date", VN) is None
    assert parse_date(None, VN) is None


def test_strip_html():
    assert strip_html('<a href="x"><img src="y"/></a> Ông <b>Nguyễn</b>  nói') == "Ông Nguyễn nói"
    assert strip_html("plain   text") == "plain text"
    assert strip_html("") == ""


def test_redact_hides_webhook_token():
    text = "POST https://discord.com/api/webhooks/123/abcDEF-token failed"
    assert redact(text) == "POST [discord-webhook] failed"
