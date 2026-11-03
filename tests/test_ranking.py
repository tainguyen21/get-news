from conftest import NOW, make_cluster, unit

from get_news.clustering import EventMatcher
from get_news.ranking import digest_order, is_repeat, select

NO_MODEL = EventMatcher(same_event=0.9, candidate=0.6, max_candidates=3, confirm=lambda subject, candidates: None)


def clusters(category, count, axis, importance=7):
    result = []
    for i in range(count):
        vector = [0.0] * 30
        vector[axis + i] = 1.0
        result.append(make_cluster(f"{category}{i}", unit(*vector), category=category, importance=importance))
    return result


def test_fills_each_section_quota():
    pool = clusters("tech", 7, 0) + clusters("world", 7, 10)
    chosen = select(pool, {"tech": 5, "world": 5}, lambda c: True, NO_MODEL)
    assert [c.category for c in chosen].count("tech") == 5
    assert [c.category for c in chosen].count("world") == 5


def test_spare_slots_go_to_the_other_section():
    pool = clusters("tech", 8, 0) + clusters("world", 2, 10)
    chosen = select(pool, {"tech": 5, "world": 5}, lambda c: True, NO_MODEL)
    assert len(chosen) == 10
    assert [c.category for c in chosen].count("world") == 2


def test_skips_duplicates_skip_category_and_rejected_material():
    tech = clusters("tech", 3, 0)
    duplicate = make_cluster("dup", tech[0].centroid.copy(), category="tech", importance=7)
    skipped = make_cluster("skip", unit(*([0.0] * 29 + [1.0])), category="skip", importance=9)
    calls = []

    def accept(cluster):
        calls.append(cluster.id)
        return cluster.id != "tech1"

    chosen = select(tech + [duplicate, skipped], {"tech": 5, "world": 5}, accept, NO_MODEL)
    assert [c.id for c in chosen] == ["tech0", "tech2"]
    assert calls.count("tech1") == 1 and "dup" not in calls and "skip" not in calls


def test_events_already_sent_are_not_selected_again():
    tech = clusters("tech", 2, 0)
    sent_before = make_cluster("old", tech[0].centroid.copy(), category="tech")
    chosen = select(tech, {"tech": 5, "world": 5}, lambda c: True, NO_MODEL, already_sent=[sent_before])
    assert [c.id for c in chosen] == ["tech1"]


def test_is_repeat_ignores_the_cluster_itself():
    cluster = make_cluster("same", unit(1, 0))
    assert not is_repeat(cluster, [cluster], NO_MODEL)


def test_overnight_hot_items_lead_then_importance():
    low = make_cluster("low", unit(1, 0), category="tech", importance=5)
    high = make_cluster("high", unit(0, 1), category="tech", importance=9)
    pending = make_cluster("pending", unit(1, 1), category="world", importance=8, hot_pending=True)
    assert [c.id for c in digest_order([low, high, pending], NOW)] == ["pending", "high", "low"]
