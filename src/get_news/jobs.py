"""The two scheduled jobs: ingest (every 15 minutes) and digest (07:00 and 19:00)."""

from __future__ import annotations

import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import cached_property

import httpx

from get_news import clustering, discord, fulltext, hot, ranking
from get_news.clustering import EventMatcher
from get_news.config import Config
from get_news.discord import DiscordError
from get_news.llm import Gemini, Material, Summary
from get_news.models import Cluster
from get_news.sources import fetch_all
from get_news.store import Store

log = logging.getLogger(__name__)

SLOT_NAMES = ("am", "pm")
_SCORE_BATCH = 40


@dataclass
class Context:
    cfg: Config
    store: Store
    gemini: Gemini
    http: httpx.Client
    dry_run: bool
    digest_hook: discord.Webhook
    hot_hook: discord.Webhook
    ops_hook: discord.Webhook
    model_checks: int = 0

    @property
    def settings(self):
        return self.cfg.settings

    @cached_property
    def matcher(self) -> EventMatcher:
        similarity = self.settings.similarity

        def confirm(subject: list[str], candidates: list[Cluster]) -> Cluster | None:
            self.model_checks += 1
            try:
                index = self.gemini.same_event(subject, [c.headlines() for c in candidates])
            except Exception as exc:  # one bad response must not stall every future run
                log.warning("same-event check failed, treating as a new event: %s", exc)
                return None
            return candidates[index] if index is not None else None

        return EventMatcher(similarity.same_event, similarity.candidate, similarity.max_candidates, confirm)

    def local(self, now: datetime) -> datetime:
        return now.astimezone(self.cfg.tz)


# Shared steps


def score(ctx: Context, clusters: list[Cluster], now: datetime) -> bool:
    """Score unscored clusters, and rescore those that gained two or more publishers.

    Returns False if any scoring call failed; those clusters keep their previous scores.
    """
    stale = [c for c in clusters if c.importance is None or len(c.publishers()) - c.scored_publishers >= 2]
    ok = True
    for start in range(0, len(stale), _SCORE_BATCH):
        chunk = stale[start : start + _SCORE_BATCH]
        try:
            scores = ctx.gemini.score(chunk, now)
        except Exception as exc:
            log.warning("scoring failed for %d clusters: %s", len(chunk), exc)
            ok = False
            continue
        for cluster in chunk:
            if cluster.id in scores:
                cluster.importance, cluster.category = scores[cluster.id]
                cluster.scored_publishers = len(cluster.publishers())
        ctx.store.save_scores([c for c in chunk if c.id in scores])
    return ok


def summarize(ctx: Context, cluster: Cluster) -> tuple[Summary, Material, dict[str, str]]:
    material, resolved = fulltext.gather(cluster, ctx.http, ctx.settings)
    return ctx.gemini.summarize(material, ctx.local(datetime.now(UTC))), material, resolved


# Ingest


def run_ingest(ctx: Context, now: datetime | None = None) -> None:
    s = ctx.settings
    now = now or datetime.now(UTC)
    articles, errors = fetch_all(ctx.cfg.sources, ctx.http, ctx.cfg.tz)
    update_health(ctx, errors, articles, now)

    seen = ctx.store.load_seen()
    keep_after = (now - timedelta(hours=s.cluster.max_age_hours + 24)).timestamp()
    seen = {key: entry for key, entry in seen.items() if entry[0] >= keep_after}
    clusters = ctx.store.clusters_updated_since(now - timedelta(hours=s.cluster.match_window_hours))
    by_id = {c.id: c for c in clusters}
    oldest = now - timedelta(hours=s.cluster.max_age_hours)

    fresh = {}
    for article in articles:
        if article.key in seen:
            refresh_hn_points(article, by_id.get(seen[article.key][1]), now)
        elif article.key not in fresh:
            if article.published_at >= oldest:
                fresh[article.key] = article
            else:
                seen[article.key] = [now.timestamp(), None]

    # Newest first, bounded per run: after an outage the backlog drains over several runs
    # instead of one run exceeding the task timeout and saving nothing.
    backlog = sorted(fresh.values(), key=lambda a: a.published_at, reverse=True)
    new = backlog[: s.cluster.max_new_per_run]
    if new:
        vectors = ctx.gemini.embed([a.embed_text for a in new])
        assignment = clustering.assign(new, vectors, clusters, ctx.matcher, s.cluster.max_articles_per_cluster, now)
        for key, cluster_id in assignment.items():
            seen[key] = [now.timestamp(), cluster_id]

    touched = [c for c in clusters if c.touched]
    ctx.store.save_clusters(touched, timedelta(days=s.cluster.retention_days))
    ctx.store.save_seen(seen)
    log.info(
        "ingest: %d fetched, %d new (%d deferred), %d clusters touched, %d same-event checks",
        len(articles),
        len(new),
        len(backlog) - len(new),
        len(touched),
        ctx.model_checks,
    )

    process_hot(ctx, touched, now)
    check_missed_digests(ctx, now)
    if not ctx.dry_run:
        ctx.store.beat("ingest", now)


def refresh_hn_points(article, cluster: Cluster | None, now: datetime) -> None:
    """Hacker News points keep rising after first sight; keep the stored value current."""
    if article.hn_points is None or cluster is None:
        return
    for stored in cluster.articles:
        if stored.key == article.key and stored.hn_points != article.hn_points:
            stored.hn_points = article.hn_points
            cluster.updated_at = now  # rising points are new activity for the digest window
            cluster.touched = True


def update_health(ctx: Context, errors: dict[str, str | None], articles, now: datetime) -> None:
    if ctx.dry_run:
        return
    health = ctx.store.load_health()
    counts = Counter(a.source_id for a in articles)
    alerts = []
    for source_id, error in errors.items():
        h = health.setdefault(source_id, {"ok": 0, "fail": 0, "items": 0, "consecutive_failures": 0, "alerted": False})
        if error is None:
            h.update(ok=h["ok"] + 1, items=h["items"] + counts[source_id], consecutive_failures=0, alerted=False)
            h["last_ok_at"] = now
        else:
            h.update(fail=h["fail"] + 1, consecutive_failures=h["consecutive_failures"] + 1, last_error=error)
            if h["consecutive_failures"] >= ctx.settings.ops.source_failure_alert_after and not h["alerted"]:
                alerts.append(f"• `{source_id}`: {error}")
                h["alerted"] = True
    ctx.store.save_health(health)
    if alerts:
        ctx.ops_hook.send_text("⚠️ **Nguồn lỗi nhiều lần liên tiếp**\n" + "\n".join(alerts))


def process_hot(ctx: Context, touched: list[Cluster], now: datetime) -> None:
    h = ctx.settings.hot
    candidates = [c for c in touched if not c.sent and not c.hot_pending and hot.is_candidate(c, now, h)]
    if not candidates:
        return
    lookback = now - timedelta(hours=ctx.settings.dedupe.sent_lookback_hours)
    sent = ctx.store.clusters_sent_since(lookback)  # fresh read: a digest may have just sent one
    sent_ids = {c.id for c in sent}
    candidates = [c for c in candidates if c.id not in sent_ids and not ranking.is_repeat(c, sent, ctx.matcher)]
    score(ctx, candidates, now)

    local = ctx.local(now)
    day = f"{local:%Y-%m-%d}"
    quiet = hot.in_quiet_hours(local.time(), h.quiet_start, h.quiet_end)
    sent_now: list[Cluster] = []
    for cluster in sorted(candidates, key=lambda c: -(c.importance or 0)):
        if cluster.importance is None or cluster.category not in ("tech", "world"):
            continue
        if ranking.is_repeat(cluster, sent_now, ctx.matcher):
            continue
        if quiet:
            if cluster.importance >= h.score_threshold and not ctx.dry_run:
                ctx.store.set_hot_pending(cluster.id)  # leads the 07:00 digest instead
            continue
        needed = hot.required_score(ctx.store.hot_count(day), h)
        if needed is None:
            return
        if cluster.importance < needed:
            continue
        summary, material, resolved = summarize(ctx, cluster)
        ctx.hot_hook.send({**discord.hot_header(), **discord.item_payload(summary, cluster, material, resolved, "hot")})
        log.info("hot alert sent: %s (importance %s)", cluster.title, cluster.importance)
        if ctx.dry_run:
            return  # the daily counter is not advanced in dry runs, so stop after one
        ctx.store.mark_hot_sent(day, cluster.id, now)
        sent_now.append(cluster)


def slot_start(local: datetime, slot: str) -> datetime:
    hour, minute = map(int, slot.split(":"))
    return local.replace(hour=hour, minute=minute, second=0, microsecond=0)


def check_missed_digests(ctx: Context, now: datetime) -> None:
    """Alert once if a digest has not completed some minutes after its slot."""
    local = ctx.local(now)
    delay = timedelta(minutes=ctx.settings.ops.missed_digest_after_minutes)
    for slot, name in zip(ctx.settings.digest.slots, SLOT_NAMES, strict=False):
        due = slot_start(local, slot) + delay
        if not due <= local < due + timedelta(minutes=30):
            continue
        digest_id = f"{local:%Y-%m-%d}-{name}"
        state = ctx.store.get_digest(digest_id)
        if state.get("status") != "done" and not state.get("missing_alerted"):
            status = state.get("status", "chưa chạy")
            ctx.ops_hook.send_text(f"⚠️ **Bản tin {slot} ngày {local:%d/%m} chưa được gửi** (trạng thái: {status}).")
            if not ctx.dry_run:
                ctx.store.update_digest(digest_id, missing_alerted=True)


# Digest


def digest_id_for(local: datetime, slots: list[str], window: timedelta) -> tuple[str, bool]:
    """Scheduled slot id when the run is near a slot, otherwise a one-off id.

    A manual run at another time must not use up the next scheduled digest.
    """
    for slot, name in zip(slots, SLOT_NAMES, strict=False):
        start = slot_start(local, slot)
        if start - timedelta(minutes=15) <= local < start + window:
            return f"{local:%Y-%m-%d}-{name}", True
    return f"{local:%Y-%m-%d}-adhoc-{local:%H%M}", False


def run_digest(ctx: Context, now: datetime | None = None) -> None:
    s = ctx.settings
    now = now or datetime.now(UTC)
    local = ctx.local(now)
    digest_id, scheduled = digest_id_for(local, s.digest.slots, timedelta(hours=s.digest.slot_window_hours))
    state = ctx.store.get_digest(digest_id)
    if state.get("status") == "done" and not ctx.dry_run:
        log.info("digest %s already sent", digest_id)
        return
    if not ctx.dry_run:
        ctx.store.update_digest(digest_id, status="started", started_at=now)
    check_ingest_alive(ctx, now)

    pool = {c.id: c for c in ctx.store.clusters_updated_since(now - timedelta(hours=s.digest.window_hours))}
    pool.update({c.id: c for c in ctx.store.clusters_hot_pending()})
    sent = ctx.store.clusters_sent_since(now - timedelta(hours=s.dedupe.sent_lookback_hours))
    candidates = [c for c in pool.values() if not c.sent]
    candidates.sort(key=lambda c: (not c.hot_pending, -ranking.prerank(c, now)))
    candidates = candidates[: max(s.digest.candidate_pool, sum(c.hot_pending for c in candidates))]
    scored = score(ctx, candidates, now)
    for cluster in candidates:  # if scoring failed, fall back to the source's section
        cluster.category = cluster.category or cluster.category_hint

    already = state.get("sent_categories", {})
    quotas = {
        "tech": max(0, s.digest.tech_items - already.get("tech", 0)),
        "world": max(0, s.digest.world_items - already.get("world", 0)),
    }
    gathered: dict[str, tuple[Material, dict[str, str]]] = {}

    def accept(cluster: Cluster) -> bool:
        gathered[cluster.id] = fulltext.gather(cluster, ctx.http, s)
        return cluster.hot_pending or gathered[cluster.id][0].fulltext_chars >= s.digest.min_material_chars

    chosen = ranking.select(ranking.digest_order(candidates, now), quotas, accept, ctx.matcher, sent)
    with ThreadPoolExecutor(max_workers=4) as pool_exec:
        results = list(pool_exec.map(lambda c: _safe_summary(ctx, c, gathered[c.id][0]), chosen))
    ready = [(c, summary) for c, summary in zip(chosen, results, strict=True) if summary]
    problems = []
    if len(ready) < len(chosen):
        problems.append(f"{len(chosen) - len(ready)} tin không tóm tắt được")
    if not scored:
        problems.append("chấm điểm tin bị lỗi, đã xếp theo nguồn")

    if not state.get("header_posted"):
        ctx.digest_hook.send(discord.digest_header(local, len(ready)))
        if not ctx.dry_run:
            ctx.store.update_digest(digest_id, header_posted=True)
    if not ready and not state.get("sent"):
        ctx.digest_hook.send({"content": "Không có tin mới đáng chú ý trong kỳ này."})
    sections = [("hot", [c for c, _ in ready if c.hot_pending])]
    sections += [(key, [c for c, _ in ready if c.category == key and not c.hot_pending]) for key in ("tech", "world")]
    summaries = {c.id: summary for c, summary in ready}
    posted = 0
    for key, members in sections:
        if not members:
            continue
        ctx.digest_hook.send(discord.section_header(key))
        for cluster in members:
            material, resolved = gathered[cluster.id]
            color = "hot" if key == "hot" else cluster.category
            try:
                ctx.digest_hook.send(discord.item_payload(summaries[cluster.id], cluster, material, resolved, color))
            except DiscordError as exc:  # skip one rejected message, keep delivering the rest
                log.warning("discord rejected cluster %s: %s", cluster.id, exc)
                problems.append(f"Discord từ chối 1 tin ({exc})")
                continue
            posted += 1
            if not ctx.dry_run:
                ctx.store.mark_digest_sent(digest_id, cluster, now)

    if not ctx.dry_run:
        ctx.store.update_digest(digest_id, status="done", done_at=datetime.now(UTC), items=posted)
        # Overnight items get one chance, in this digest; leftovers must not resurface days later.
        sent_ids = {c.id for c, _ in ready}
        ctx.store.clear_hot_pending([c.id for c in pool.values() if c.hot_pending and c.id not in sent_ids])
        ctx.store.beat("digest", now)
    log.info("digest %s: %d items posted; problems: %s", digest_id, posted, problems or "none")
    if problems:
        ctx.ops_hook.send_text(f"⚠️ **Bản tin {digest_id}**: " + "; ".join(problems) + ".")
    if scheduled and digest_id.endswith(SLOT_NAMES[0]) and local.weekday() == 0:
        weekly_report(ctx)


def check_ingest_alive(ctx: Context, now: datetime) -> None:
    """Ingest can die without reporting (timeout, crash); the digest notices a stale heartbeat."""
    last = ctx.store.last_beat("ingest")
    limit = timedelta(minutes=ctx.settings.ops.ingest_stale_after_minutes)
    if last is None or now - last > limit:
        since = ctx.local(last).strftime("%H:%M %d/%m") if last else "chưa từng"
        ctx.ops_hook.send_text(f"⚠️ **Job ingest không chạy thành công từ {since}**: bản tin có thể thiếu tin mới.")


def _safe_summary(ctx: Context, cluster: Cluster, material: Material) -> Summary | None:
    try:
        return ctx.gemini.summarize(material, ctx.local(datetime.now(UTC)))
    except Exception:
        log.exception("summary failed for cluster %s", cluster.id)
        return None


def weekly_report(ctx: Context) -> None:
    health = ctx.store.load_health()
    lines = ["📊 **Báo cáo nguồn tin 7 ngày qua**"]
    for source in ctx.cfg.sources:
        h = health.get(source.id)
        if not h or not h["ok"] + h["fail"]:
            lines.append(f"❔ `{source.id}`: chưa có dữ liệu")
            continue
        rate = h["ok"] / (h["ok"] + h["fail"])
        line = f"{'✅' if rate >= 0.9 else '⚠️'} `{source.id}`: {rate:.0%} lần chạy thành công, {h['items']} bài"
        if rate < 0.9 and h.get("last_error"):
            line += f" — lỗi gần nhất: {h['last_error'][:120]}"
        lines.append(line)
    ctx.ops_hook.send_text("\n".join(lines))
    if not ctx.dry_run:
        for h in health.values():
            h.update(ok=0, fail=0, items=0)
        ctx.store.save_health(health)
