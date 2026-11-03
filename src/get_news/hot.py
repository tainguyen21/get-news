"""Rules for hot-news alerts: who qualifies, when to stay quiet, and the daily cap."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from types import SimpleNamespace

from get_news.models import Cluster


def is_candidate(cluster: Cluster, now: datetime, hot: SimpleNamespace) -> bool:
    """Several independent publishers in a short window, or a fast-rising Hacker News story."""
    recent = cluster.publishers(since=now - timedelta(hours=hot.publisher_window_hours))
    if len(recent) >= hot.min_publishers:
        return True
    for article in cluster.articles:
        if (article.hn_points or 0) < hot.hn_min_points:
            continue
        hours = (now - article.published_at).total_seconds() / 3600
        if hours <= hot.hn_max_age_hours and article.hn_points / max(hours, 0.5) >= hot.hn_min_points_per_hour:
            return True
    return False


def in_quiet_hours(local: time, start: str, end: str) -> bool:
    begin, finish = time.fromisoformat(start), time.fromisoformat(end)
    if begin <= finish:
        return begin <= local < finish
    return local >= begin or local < finish  # window wraps past midnight


def required_score(sent_today: int, hot: SimpleNamespace) -> int | None:
    """Minimum importance for the next alert today, or None when the daily cap is reached."""
    if sent_today >= hot.max_per_day:
        return None
    if sent_today == hot.max_per_day - 1:
        return hot.last_slot_threshold
    return hot.score_threshold
