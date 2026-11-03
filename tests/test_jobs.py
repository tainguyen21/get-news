"""Digest job behaviour with in-memory stand-ins for Firestore, Gemini and Discord."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from conftest import NOW, make_article, make_cluster, unit

from get_news import jobs
from get_news.config import Config, Webhooks
from get_news.discord import DiscordError
from get_news.llm import Material, Summary

VN = ZoneInfo("Asia/Ho_Chi_Minh")


class MemoryStore:
    def __init__(self, clusters):
        self.clusters = {c.id: c for c in clusters}
        self.digests: dict[str, dict] = {}
        self.beats: dict[str, datetime] = {}

    def get_digest(self, digest_id):
        return dict(self.digests.get(digest_id, {}))

    def update_digest(self, digest_id, **fields):
        self.digests.setdefault(digest_id, {}).update(fields)

    def mark_digest_sent(self, digest_id, cluster, now):
        cluster.digest_sent_at, cluster.hot_pending = now, False
        doc = self.digests.setdefault(digest_id, {})
        doc.setdefault("sent", []).append(cluster.id)
        counts = doc.setdefault("sent_categories", {})
        counts[cluster.category] = counts.get(cluster.category, 0) + 1

    def clusters_updated_since(self, since):
        return [c for c in self.clusters.values() if c.updated_at >= since]

    def clusters_hot_pending(self):
        return [c for c in self.clusters.values() if c.hot_pending]

    def clusters_sent_since(self, since):
        return [c for c in self.clusters.values() if (c.digest_sent_at or c.hot_sent_at or since - timedelta(1)) >= since]

    def clear_hot_pending(self, ids):
        for cluster_id in ids:
            self.clusters[cluster_id].hot_pending = False

    def save_scores(self, clusters):
        pass

    def beat(self, job, now):
        self.beats[job] = now

    def last_beat(self, job):
        return self.beats.get(job)


class FakeGemini:
    def score(self, clusters, now):
        return {c.id: (7, c.category_hint) for c in clusters}

    def summarize(self, material, local_now):
        return Summary(title="Tiêu đề", lead="Câu dẫn.", points=["Ý chính."], discrepancy="")

    def same_event(self, subject, candidates):
        return None


class Recorder:
    def __init__(self, fail_on=None):
        self.sent, self.texts, self.fail_on = [], [], fail_on

    def send(self, payload):
        if self.fail_on and self.fail_on in str(payload):
            raise DiscordError("Discord HTTP 400: bad embed")
        self.sent.append(payload)

    def send_text(self, text):
        self.texts.append(text)


def context(settings, clusters, digest_hook=None, gemini=None):
    cfg = Config(settings=settings, sources=[], project="test", location="global", webhooks=Webhooks(None, None, None))
    return jobs.Context(
        cfg=cfg,
        store=MemoryStore(clusters),
        gemini=gemini or FakeGemini(),
        http=None,
        dry_run=False,
        digest_hook=digest_hook or Recorder(),
        hot_hook=Recorder(),
        ops_hook=Recorder(),
    )


@pytest.fixture(autouse=True)
def full_text(monkeypatch):
    material = Material(texts=[("BBC", "https://bbc.co.uk/x", "t", "x" * 2000)], headlines=[], image=None)
    monkeypatch.setattr(jobs.fulltext, "gather", lambda cluster, http, settings: (material, {}))


def tech_and_world_clusters(count=3):
    result = []
    for i in range(count):
        for axis, category in ((0, "tech"), (10, "world")):
            vector = [0.0] * 30
            vector[axis + i] = 1.0
            article = make_article(f"{category}{i}.com", url=f"https://{category}{i}.com/a", title=f"{category} story {i}")
            cluster = make_cluster(f"{category}{i}", unit(*vector), [article])
            cluster.category_hint = category
            result.append(cluster)
    return result


@pytest.mark.parametrize(
    ("local_time", "expected", "scheduled"),
    [
        ("07:00", "2026-11-03-am", True),
        ("06:50", "2026-11-03-am", True),
        ("19:40", "2026-11-03-pm", True),
        ("16:00", "2026-11-03-adhoc-1600", False),
    ],
)
def test_manual_runs_outside_a_slot_do_not_use_up_the_slot(local_time, expected, scheduled):
    hour, minute = map(int, local_time.split(":"))
    local = datetime(2026, 11, 3, hour, minute, tzinfo=VN)
    assert jobs.digest_id_for(local, ["07:00", "19:00"], timedelta(hours=3)) == (expected, scheduled)


def test_digest_posts_sections_marks_sent_and_runs_once(settings):
    ctx = context(settings, tech_and_world_clusters())
    now = datetime(2026, 11, 3, 0, 1, tzinfo=UTC)  # 07:01 in Vietnam
    ctx.store.beat("ingest", now)
    for cluster in ctx.store.clusters.values():
        cluster.updated_at = now
        cluster.articles[0].published_at = now

    jobs.run_digest(ctx, now)

    contents = [p.get("content", "") for p in ctx.digest_hook.sent]
    assert "BẢN TIN SÁNG" in contents[0]
    assert sum("embeds" in p for p in ctx.digest_hook.sent) == 6
    assert ctx.store.digests["2026-11-03-am"]["status"] == "done"
    assert all(c.digest_sent_at == now for c in ctx.store.clusters.values())
    assert ctx.ops_hook.texts == []

    posted = len(ctx.digest_hook.sent)
    jobs.run_digest(ctx, now + timedelta(minutes=5))
    assert len(ctx.digest_hook.sent) == posted


def test_unsent_overnight_items_are_cleared_after_the_digest(settings):
    clusters = tech_and_world_clusters(1)
    duplicate = make_cluster("dup", clusters[0].centroid.copy(), [make_article("x.com")], hot_pending=True)
    clusters[0].hot_pending = True
    ctx = context(settings, clusters + [duplicate])
    now = datetime(2026, 11, 3, 0, 1, tzinfo=UTC)
    for cluster in ctx.store.clusters.values():
        cluster.updated_at = now

    jobs.run_digest(ctx, now)

    assert clusters[0].digest_sent_at == now
    assert duplicate.digest_sent_at is None and duplicate.hot_pending is False


def test_one_rejected_message_does_not_stop_the_digest(settings):
    # Summaries are identical, so the rejected message is identified by its source link.
    ctx = context(settings, tech_and_world_clusters(), digest_hook=Recorder(fail_on="tech0.com"))
    now = datetime(2026, 11, 3, 0, 1, tzinfo=UTC)
    ctx.store.beat("ingest", now)
    for cluster in ctx.store.clusters.values():
        cluster.updated_at = now

    jobs.run_digest(ctx, now)

    assert sum("embeds" in p for p in ctx.digest_hook.sent) == 5
    assert ctx.store.clusters["tech0"].digest_sent_at is None
    assert ctx.store.digests["2026-11-03-am"]["status"] == "done"
    assert any("Discord từ chối" in text for text in ctx.ops_hook.texts)


def test_stale_ingest_is_reported_by_the_digest(settings):
    ctx = context(settings, [])
    ctx.store.beat("ingest", NOW - timedelta(hours=3))
    jobs.check_ingest_alive(ctx, NOW)
    assert any("ingest không chạy" in text for text in ctx.ops_hook.texts)


def test_failed_same_event_check_counts_as_a_new_event(settings):
    class BrokenGemini(FakeGemini):
        def same_event(self, subject, candidates):
            raise ValueError("empty response")

    ctx = context(settings, [], gemini=BrokenGemini())
    candidate = make_cluster("c", unit(1, 0.8))
    assert ctx.matcher.match(unit(1, 0), ["headline"], [candidate]) is None
    assert ctx.model_checks == 1


def test_scoring_failure_falls_back_to_source_sections(settings):
    class NoScoring(FakeGemini):
        def score(self, clusters, now):
            raise RuntimeError("quota exceeded")

    ctx = context(settings, tech_and_world_clusters(), gemini=NoScoring())
    now = datetime(2026, 11, 3, 12, 1, tzinfo=UTC)  # 19:01 in Vietnam
    ctx.store.beat("ingest", now)
    for cluster in ctx.store.clusters.values():
        cluster.updated_at = now

    jobs.run_digest(ctx, now)

    assert sum("embeds" in p for p in ctx.digest_hook.sent) == 6
    assert any("chấm điểm" in text for text in ctx.ops_hook.texts)
