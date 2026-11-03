from datetime import time

from conftest import NOW, make_article, make_cluster, unit

from get_news.hot import in_quiet_hours, is_candidate, required_score


def test_three_recent_publishers_make_a_candidate(settings):
    recent = [make_article(d, minutes_ago=30) for d in ("a.com", "b.com", "c.com")]
    assert is_candidate(make_cluster("c", unit(1, 0), recent), NOW, settings.hot)


def test_old_reports_do_not_count_toward_the_window(settings):
    articles = [make_article("a.com", 30), make_article("b.com", 40), make_article("c.com", 180)]
    assert not is_candidate(make_cluster("c", unit(1, 0), articles), NOW, settings.hot)


def test_fast_rising_hacker_news_story_is_a_candidate(settings):
    rising = make_article("blog.dev", minutes_ago=120, hn_points=400)  # 200 points per hour
    slow = make_article("blog.dev", minutes_ago=300, hn_points=250)  # 50 points per hour
    assert is_candidate(make_cluster("c", unit(1, 0), [rising]), NOW, settings.hot)
    assert not is_candidate(make_cluster("c", unit(1, 0), [slow]), NOW, settings.hot)


def test_old_hacker_news_story_is_not_breaking_news(settings):
    old = make_article("blog.dev", minutes_ago=16 * 60, hn_points=2133)  # 133 points per hour
    assert not is_candidate(make_cluster("c", unit(1, 0), [old]), NOW, settings.hot)


def test_quiet_hours_wrap_past_midnight():
    assert in_quiet_hours(time(23, 30), "23:00", "07:00")
    assert in_quiet_hours(time(6, 59), "23:00", "07:00")
    assert not in_quiet_hours(time(7, 0), "23:00", "07:00")
    assert not in_quiet_hours(time(14, 0), "23:00", "07:00")


def test_daily_cap_and_stricter_last_slot(settings):
    assert required_score(0, settings.hot) == 8
    assert required_score(1, settings.hot) == 8
    assert required_score(2, settings.hot) == 9
    assert required_score(3, settings.hot) is None
