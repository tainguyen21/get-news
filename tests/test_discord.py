import httpx
import pytest
from conftest import make_article, make_cluster, unit

from get_news.discord import DiscordError, Webhook, item_payload
from get_news.llm import Material, Summary

WEBHOOK = "https://discord.com/api/webhooks/1/secret-token"


def summary(points=5, length=80):
    return Summary(title="Tiêu đề", lead="Câu dẫn.", points=["ý " + "x" * length] * points, discrepancy="")


def cluster_with_sources():
    articles = [
        make_article("reuters.com", url="https://news.google.com/rss/articles/abc", source_name="Reuters", gnews=True),
        make_article("bbc.co.uk", url="https://bbc.co.uk/news/1", source_name="BBC"),
    ]
    return make_cluster("c1", unit(1, 0), articles, category="world")


def test_item_payload_formats_lead_points_and_sources():
    cluster = cluster_with_sources()
    material = Material(texts=[], headlines=[], image="https://img.example/a.jpg")
    resolved = {cluster.articles[0].key: "https://reuters.com/world/x"}
    embed = item_payload(summary(), cluster, material, resolved, "world")["embeds"][0]
    assert embed["description"].startswith("**Câu dẫn.**\n\n• ý")
    assert "[Reuters](https://reuters.com/world/x)" in embed["description"]
    assert embed["url"] == "https://reuters.com/world/x"
    assert embed["image"] == {"url": "https://img.example/a.jpg"}
    assert embed["footer"]["text"] == "Thế giới · 2 nguồn"


def test_item_payload_respects_discord_description_limit():
    cluster = cluster_with_sources()
    embed = item_payload(summary(points=40, length=200), cluster, Material([], [], None), {}, "tech")["embeds"][0]
    assert len(embed["description"]) <= 4096
    assert embed["description"].rstrip().endswith(")")  # source line survives trimming
    assert "image" not in embed


def test_webhook_retries_after_rate_limit(monkeypatch):
    monkeypatch.setattr("get_news.discord.time.sleep", lambda seconds: None)
    responses = iter([httpx.Response(429, json={"retry_after": 0.5}), httpx.Response(200, json={"id": "1"})])
    requests = []

    def handler(request):
        requests.append(request)
        return next(responses)

    hook = Webhook(WEBHOOK, httpx.Client(transport=httpx.MockTransport(handler)), "Bản tin", dry_run=False)
    hook.send({"content": "hi"})
    assert len(requests) == 2
    assert requests[0].url.params["wait"] == "true"


def test_webhook_error_does_not_leak_token():
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(404, text="Unknown Webhook")))
    with pytest.raises(DiscordError) as error:
        Webhook(WEBHOOK, client, "Bản tin", dry_run=False).send({"content": "hi"})
    assert "secret-token" not in str(error.value)


def test_send_text_splits_long_messages():
    sent = []
    hook = Webhook(None, httpx.Client(), "Hệ thống", dry_run=True)
    hook.send = sent.append
    hook.send_text("\n".join(f"dòng {i} " + "y" * 90 for i in range(60)))
    assert len(sent) > 1 and all(len(p["content"]) <= 2000 for p in sent)
