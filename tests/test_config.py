"""The real sources.yaml and settings.yaml must load and contain every key the jobs read."""

from conftest import ROOT

from get_news.config import load_settings, load_sources
from get_news.sources import PARSERS

REQUIRED_SETTINGS = [
    "timezone", "topic_priorities", "topic_low_priority", "topic_skip",
    "models.embedding", "models.embedding_dims", "models.scoring", "models.summary",
    "similarity.same_event", "similarity.candidate", "similarity.max_candidates",
    "cluster.match_window_hours", "cluster.max_age_hours", "cluster.max_articles_per_cluster",
    "cluster.max_new_per_run", "cluster.retention_days", "dedupe.sent_lookback_hours",
    "digest.slots", "digest.slot_window_hours", "digest.tech_items", "digest.world_items",
    "digest.window_hours", "digest.candidate_pool", "digest.min_material_chars",
    "digest.max_fulltext_articles", "digest.max_article_chars",
    "hot.min_publishers", "hot.publisher_window_hours", "hot.hn_min_points", "hot.hn_min_points_per_hour",
    "hot.hn_max_age_hours", "hot.score_threshold", "hot.last_slot_threshold", "hot.max_per_day",
    "hot.quiet_start", "hot.quiet_end", "fulltext_skip_domains",
    "ops.source_failure_alert_after", "ops.missed_digest_after_minutes", "ops.ingest_stale_after_minutes",
]


def test_settings_have_every_key_the_jobs_read():
    settings = load_settings(ROOT)
    for path in REQUIRED_SETTINGS:
        node = settings
        for part in path.split("."):
            assert hasattr(node, part), f"settings.yaml is missing {path}"
            node = getattr(node, part)
    assert settings.similarity.candidate < settings.similarity.same_event
    assert len(settings.digest.slots) <= 2  # slots map to the am and pm digests


def test_sources_are_valid():
    sources = load_sources(ROOT)
    assert sources
    assert len({s.id for s in sources}) == len(sources), "duplicate source id"
    for source in sources:
        assert source.kind in PARSERS, f"{source.id}: unknown kind {source.kind}"
        assert source.category in ("tech", "world"), f"{source.id}: category must be tech or world"
        assert source.url.startswith("https://"), f"{source.id}: url must be https"
