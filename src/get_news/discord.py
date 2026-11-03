"""Discord webhook delivery and message formatting."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime

import httpx

from get_news.llm import Material, Summary
from get_news.models import Cluster

log = logging.getLogger(__name__)

DESCRIPTION_LIMIT = 4000  # Discord allows 4096 per embed description
CONTENT_LIMIT = 1900  # Discord allows 2000 per message content
COLORS = {"tech": 0x3B82F6, "world": 0x10B981, "hot": 0xEF4444}
SECTION_LABELS = {"tech": "Công nghệ", "world": "Thế giới"}
WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]


class DiscordError(RuntimeError):
    pass


class Webhook:
    """One channel's webhook. Without a URL, or in dry-run mode, payloads are printed instead."""

    def __init__(self, url: str | None, http: httpx.Client, username: str, dry_run: bool):
        self.url = url
        self.http = http
        self.username = username
        self.dry_run = dry_run

    def send(self, payload: dict) -> None:
        body = {"username": self.username, "allowed_mentions": {"parse": []}, **payload}
        if self.dry_run or not self.url:
            print(f"--- [{self.username}] ---\n{json.dumps(payload, ensure_ascii=False, indent=2)}", flush=True)
            return
        for attempt in range(5):
            try:
                response = self.http.post(self.url, params={"wait": "true"}, json=body)
            except httpx.TransportError as exc:  # network blip or timeout: retry
                log.warning("discord %s: %s", self.username, type(exc).__name__)
                time.sleep(2**attempt)
                continue
            if response.status_code == 429:
                time.sleep(float(response.json().get("retry_after", 1)) + 0.2)
                continue
            if response.status_code >= 500:
                time.sleep(2**attempt)
                continue
            if response.is_error:
                # Never include the URL: it contains the webhook token.
                raise DiscordError(f"Discord HTTP {response.status_code}: {response.text[:300]}")
            if response.headers.get("X-RateLimit-Remaining") == "0":
                time.sleep(float(response.headers.get("X-RateLimit-Reset-After", 1)))
            return
        raise DiscordError(f"Discord webhook '{self.username}' failed after retries")

    def send_text(self, text: str) -> None:
        """Plain message, split on line boundaries to respect the content limit."""
        chunk = ""
        for line in text.splitlines():
            if chunk and len(chunk) + len(line) + 1 > CONTENT_LIMIT:
                self.send({"content": chunk})
                chunk = ""
            chunk = f"{chunk}\n{line}" if chunk else line[:CONTENT_LIMIT]
        if chunk:
            self.send({"content": chunk})


def _sources(cluster: Cluster, resolved: dict[str, str]) -> list[tuple[str, str]]:
    seen, links = set(), []
    for article in cluster.articles:
        if article.domain in seen:
            continue
        seen.add(article.domain)
        links.append((article.source_name, resolved.get(article.key, article.url)))
    return links


def item_payload(
    summary: Summary,
    cluster: Cluster,
    material: Material,
    resolved: dict[str, str],
    color_key: str,
) -> dict:
    """One embed: bold lead, every main point as a bullet, discrepancy note, source links."""
    sources = _sources(cluster, resolved)
    source_line = "Nguồn: " + " · ".join(f"[{name}]({url})" for name, url in sources[:6])
    body = f"**{summary.lead}**\n\n" + "\n".join(f"• {point}" for point in summary.points)
    if summary.discrepancy:
        body += f"\n\n⚠️ {summary.discrepancy}"
    room = DESCRIPTION_LIMIT - len(source_line) - 2
    if len(body) > room:
        body = body[: room - 1].rstrip() + "…"
    primary = next((url for name, url in sources if "news.google.com" not in url), sources[0][1])
    embed = {
        "title": summary.title[:256],
        "url": primary,
        "description": f"{body}\n\n{source_line}",
        "color": COLORS[color_key],
        "footer": {"text": f"{SECTION_LABELS.get(cluster.category, '')} · {len(cluster.publishers())} nguồn"},
        "timestamp": min(a.published_at for a in cluster.articles).isoformat(),
    }
    if material.image:
        embed["image"] = {"url": material.image}
    return {"embeds": [embed]}


def digest_header(local: datetime, items: int) -> dict:
    session = "SÁNG" if local.hour < 12 else "TỐI"
    return {"content": f"📰 **BẢN TIN {session}** · {WEEKDAYS[local.weekday()]} {local:%d/%m/%Y} · {items} tin"}


def section_header(key: str) -> dict:
    labels = {"hot": "🚨 **TIN NÓNG QUA ĐÊM**", "tech": "💻 **CÔNG NGHỆ**", "world": "🌍 **THẾ GIỚI**"}
    return {"content": labels[key]}


def hot_header() -> dict:
    return {"content": "🚨 **TIN NÓNG**"}
