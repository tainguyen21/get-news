import numpy as np
from conftest import NOW, make_article, make_cluster, unit

from get_news.clustering import EventMatcher, assign


def matcher(confirm=lambda subject, candidates: None, calls=None):
    def recording(subject, candidates):
        if calls is not None:
            calls.append((subject, [c.id for c in candidates]))
        return confirm(subject, candidates)

    return EventMatcher(same_event=0.9, candidate=0.6, max_candidates=3, confirm=recording)


def test_clear_match_joins_without_asking_the_model():
    calls = []
    cluster = make_cluster("c1", unit(1, 0))
    assert matcher(calls=calls).match(unit(0.99, 0.1), ["x"], [cluster]) is cluster
    assert calls == []


def test_ambiguous_match_is_decided_by_the_model():
    calls = []
    near, far = make_cluster("near", unit(1, 0.6)), make_cluster("far", unit(0, 1))
    chosen = matcher(lambda s, cands: cands[0], calls).match(unit(1, 0), ["headline"], [far, near])
    assert chosen is near
    assert calls == [(["headline"], ["near"])]  # "far" is below the candidate threshold


def test_model_can_reject_an_ambiguous_match():
    assert matcher().match(unit(1, 0), ["x"], [make_cluster("c", unit(1, 0.6))]) is None


def test_assign_joins_known_events_and_starts_new_ones():
    existing = make_cluster("c1", unit(1, 0, 0))
    clusters = [existing]
    joining = make_article("a.com", url="https://a.com/1")
    separate = make_article("b.com", url="https://b.com/1")
    vectors = np.stack([unit(0.99, 0.1, 0), unit(0, 0, 1)])

    assignment = assign([joining, separate], vectors, clusters, matcher(), max_articles=20, now=NOW)

    assert assignment[joining.key] == "c1"
    assert assignment[separate.key] != "c1"
    assert len(clusters) == 2
    assert existing.touched and existing.count == 2
    assert np.isclose(np.linalg.norm(existing.centroid), 1.0)


def test_articles_in_same_batch_can_form_a_new_cluster_together():
    clusters = []
    first = make_article("a.com", url="https://a.com/x")
    second = make_article("b.com", url="https://b.com/x")
    assign([first, second], np.stack([unit(0, 1, 0), unit(0.05, 1, 0)]), clusters, matcher(), 20, NOW)
    assert len(clusters) == 1 and clusters[0].publishers() == {"a.com", "b.com"}


def test_article_list_is_capped_but_count_keeps_growing():
    cluster = make_cluster("c1", unit(1, 0))
    articles = [make_article(f"s{i}.com", url=f"https://s{i}.com/x") for i in range(5)]
    assign(articles, np.stack([unit(1, 0)] * 5), [cluster], matcher(), max_articles=3, now=NOW)
    assert len(cluster.articles) == 3 and cluster.count == 6
