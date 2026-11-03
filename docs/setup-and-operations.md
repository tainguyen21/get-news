# get-news: setup and operations

A personal news digest. Two Cloud Run Jobs on Google Cloud collect technology and world
news, group articles about the same event, and post Vietnamese summaries to Discord:

- `get-news-ingest` runs every 15 minutes, at minutes 05, 20, 35 and 50 so it never overlaps
  a digest. It fetches every source in `sources.yaml`, skips articles already seen, embeds up
  to `cluster.max_new_per_run` new ones (newest first; a backlog drains over later runs),
  assigns them to event clusters, and sends hot-news alerts to `#tin-nong`.
- `get-news-digest` runs at 07:00 and 19:00 (Asia/Ho_Chi_Minh). It picks about 5 technology
  and 5 world events from the last 12 hours, reads full article text, and posts one message
  per event to `#tin-tuc`: title, bold lead sentence, every main point as a bullet, original
  image, and source links.
- `#he-thong` receives job errors (including configuration errors and timeouts), sources that
  fail several runs in a row, digests that have not completed 30 minutes after their slot,
  digests that find ingest has not succeeded for an hour, and a source-health report every
  Monday morning.

## Architecture

| Piece | Where |
|---|---|
| Code | `src/get_news/` (`__main__.py` is the entry point: `python -m get_news ingest\|digest [--dry-run]`) |
| Sources | `sources.yaml` |
| Tuning (topics, thresholds, models, schedule slots) | `settings.yaml` |
| State | Firestore `(default)` database: `clusters`, `digests`, `state` collections (see `store.py`) |
| Models | Vertex AI global endpoint: `gemini-embedding-001`, `gemini-3.1-flash-lite` (scoring and same-event checks), `gemini-3.8-flash` (summaries) |
| Secrets | Secret Manager: `discord-webhook-digest`, `discord-webhook-hot`, `discord-webhook-ops` |
| Deploy | `deploy.sh` (idempotent) |

### How events are grouped

Each article's title and snippet are embedded. Cosine similarity to recent clusters settles
clear cases: at or above `similarity.same_event` the article joins the cluster, below
`similarity.candidate` it starts a new one. In between, the scoring model is asked whether the
article reports the same specific event. Embeddings alone could not separate "same event" from
"same topic" on real articles, so this middle band matters. The same check prevents an event
from being sent twice within `dedupe.sent_lookback_hours`.

### Hot news

An event qualifies when at least `hot.min_publishers` independent publishers report it within
`hot.publisher_window_hours`, or when a Hacker News story younger than `hot.hn_max_age_hours`
gains points fast. The scoring model then rates importance 1-10; alerts need
`hot.score_threshold` (the last daily slot needs `hot.last_slot_threshold`), at most
`hot.max_per_day` per day. Between `quiet_start` and `quiet_end`, qualifying events are held and
lead the 07:00 digest instead.

## First-time setup

1. Create a GCP project, link billing, and authenticate gcloud (`gcloud auth login`).
2. Create three Discord webhooks (channel settings, Integrations, Webhooks) for `#tin-tuc`,
   `#tin-nong` and `#he-thong`.
3. `cp .env.example .env` and fill in `GCP_PROJECT`, `GCP_REGION` and the three webhook URLs.
   `.env` is git-ignored and excluded from Cloud Build uploads.
4. Run `./deploy.sh` from Git Bash or any bash shell.

The free trial ends after 90 days or when its credit is used. Upgrade the billing account to a
paid account before then, or every job stops and the project's resources are deleted 30 days
later. Budget alerts at $10 and $20 are emailed to billing administrators.

## Everyday operations

| Task | Command |
|---|---|
| Change sources or tuning | Edit `sources.yaml` / `settings.yaml`, then `./deploy.sh` |
| Run a job now | `gcloud run jobs execute get-news-digest --region=us-central1 --project=$GCP_PROJECT` |
| Pause everything | `gcloud scheduler jobs pause get-news-ingest --location=us-central1` (same for `get-news-digest`) |
| Resume | `gcloud scheduler jobs resume ...` |
| Read logs | `gcloud logging read 'resource.type="cloud_run_job"' --project=$GCP_PROJECT --limit=50` |
| Rotate a webhook | Update `.env`, rerun `./deploy.sh` (it adds a new secret version only when the value changed) |

A run within `digest.slot_window_hours` of 07:00 or 19:00 belongs to that slot, and each slot
runs once: the `digests/{date}-{am|pm}` document records progress, so a retry continues where
it stopped and never posts an item twice. A manual run at any other time is a one-off digest
(`{date}-adhoc-{HHMM}`) and does not use up the next scheduled one; events it posts are not
repeated later. If you change the digest times, update both `digest.slots` and the digest cron
in `deploy.sh`.

## Local development

```bash
uv sync
uv run pytest
# Real sources, Gemini and Firestore; prints Discord messages instead of sending them.
GCP_PROJECT=<project> GET_NEWS_GCLOUD_AUTH=1 uv run python -m get_news ingest --dry-run
GCP_PROJECT=<project> GET_NEWS_GCLOUD_AUTH=1 uv run python -m get_news digest --dry-run
```

`GET_NEWS_GCLOUD_AUTH=1` uses the active gcloud user's token, for machines whose
application-default credentials belong to another account. A dry run never posts to Discord
and never records anything as sent, but ingest still stores clusters.

## Costs (estimates)

Cloud Run, Scheduler (2 of 3 free jobs), Secret Manager and Logging stay within their free
tiers in `us-central1`. Firestore writes stay within the free tier; reads are likely somewhat
above the free 50,000 per day, because each ingest reads the clusters of the last 24 hours, which
costs cents per month. Gemini is the main cost: roughly $7 per month at 2026
prices and $12-15 from 2027-01-01, when Gemini 3.8 Flash doubles in price. Setting
`models.summary` to `gemini-3.5-flash-lite` cuts summary cost about threefold if its Vietnamese
quality is acceptable.

## Known limits

- Ars Technica blocks scripted access, and The Verge and NYT have paywalls; their headlines
  still count toward an event, and full text comes from other publishers.
- Reddit is not a source: it closed free access in 2026.
- Google News RSS answers HTTP 503 to requests from Cloud Run (it works from home connections),
  so its sources are disabled in `sources.yaml`, and Reuters and AP headlines are unavailable.
  World coverage comes from direct feeds (BBC, The Guardian, Al Jazeera, NYT, DW) checked from
  Cloud Run on 2026-11-03. NPR and France 24 returned HTTP 403 from Cloud Run.
- Thresholds in `settings.yaml` are initial values and may need tuning after a week of use.
- `deploy.sh` runs the test suite first, which also checks that `sources.yaml` and
  `settings.yaml` contain every required key.
