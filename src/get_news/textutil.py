"""URL, date and text helpers shared by the fetchers and the jobs."""

from __future__ import annotations

import email.utils
import hashlib
import re
from datetime import UTC, datetime, tzinfo
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import lxml.html
from tld import get_fld

_TRACKING_PARAM = re.compile(r"^(utm_|at_|fbclid$|gclid$|ocid$|cmpid$|ref$|ref_src$|smid$|taid$)")
_SHORT_TZ = re.compile(r"([+-]\d{2})$")  # "+07" -> "+0700" (Genk)
_WEBHOOK_URL = re.compile(r"https://(?:\w+\.)?discord(?:app)?\.com/api/(?:v\d+/)?webhooks/\S+")
_FALLBACK_FORMATS = ("%m/%d/%Y %I:%M:%S %p",)  # Tuoi Tre: "11/3/2026 9:48:00 AM", no zone


def canonical_url(url: str) -> str:
    """Drop tracking parameters and fragments so the same article maps to one key."""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _TRACKING_PARAM.match(k)]
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower() or "https", host, path, urlencode(query), ""))


def url_key(url: str) -> str:
    """Stable short id for an article URL, independent of scheme and tracking noise."""
    parts = urlsplit(canonical_url(url))
    return hashlib.sha1(f"{parts.netloc}{parts.path}?{parts.query}".encode()).hexdigest()[:16]


def domain_of(url: str) -> str:
    """Registered domain (bbc.co.uk, cnn.com) used to count independent publishers."""
    fld = get_fld(url, fail_silently=True, fix_protocol=True)
    if fld:
        return fld.lower()
    return urlsplit(url).netloc.lower().removeprefix("www.")


def strip_html(text: str | None) -> str:
    if not text or not text.strip():
        return ""
    if "<" not in text:
        return " ".join(text.split())
    try:
        content = lxml.html.fragment_fromstring(text, create_parent="div").text_content()
    except (lxml.etree.ParserError, ValueError):
        return " ".join(re.sub(r"<[^>]+>", " ", text).split())
    return " ".join(content.split())


def parse_date(raw: str | None, default_tz: tzinfo) -> datetime | None:
    """Parse feed dates, including the non-standard Vietnamese feed formats, to UTC."""
    if not raw:
        return None
    text = _SHORT_TZ.sub(r"\g<1>00", raw.replace(" ", " ").strip())
    parsed: datetime | None = None
    try:
        parsed = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        for fmt in _FALLBACK_FORMATS:
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError:
                return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=default_tz)
    return parsed.astimezone(UTC)


def redact(text: str) -> str:
    """Remove Discord webhook URLs (they embed a secret token) from log and alert text."""
    return _WEBHOOK_URL.sub("[discord-webhook]", text)
