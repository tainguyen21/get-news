---
title: Deploy get-news digest on GCP
date: 2026-11-03
summary: Built and deployed the Vietnamese news digest on Cloud Run Jobs; event matching and source access needed live fixes
---

# Deploy get-news digest on GCP

## What happened

Built the personal news digest from plan `plans/261103-0355-news-digest-discord-gcp` and deployed it to the new project `get-news-dg-261103` (us-central1): two Cloud Run Jobs (`get-news-ingest` at minutes 05/20/35/50, `get-news-digest` at 07:00 and 19:00 Asia/Ho_Chi_Minh), Firestore state, Secret Manager webhooks, Gemini on the Vertex AI global endpoint.

Live verification on 2026-11-03: ingest on Cloud Run fetched 941 items from 26 sources; a real digest posted 10 items to `#tin-tuc` in 92 s; a forced startup failure (empty `GCP_PROJECT` override) reached `#he-thong`. 49 unit tests pass.

## Problems found and their causes

- Event grouping: `gemini-embedding-001` with the `CLUSTERING` task type could not separate "same event" from "same topic" on labeled real pairs (margin +0.013); Vietnamese articles on unrelated topics scored 0.93. Without a task type, margin was best but still thin.
- Google News RSS answers HTTP 503 to Cloud Run egress, consistently across runs, while it works from a home connection. NPR and France 24 return 403 from Cloud Run.
- Budget creation failed with `INVALID_ARGUMENT` because the billing account currency is VND, not USD.
- Independent review found four high issues: ingest saved nothing if it exceeded the task timeout, startup and config errors were never reported, a manual digest run consumed the next scheduled slot, and unsent `hot_pending` clusters could resurface days later.
- Git Bash rewrites absolute paths such as `/app/.venv/bin/python` passed to gcloud; relative paths avoid it.

## Decisions

- Two-tier matcher: cosine ≥ 0.88 joins, < 0.66 starts a new event, the band in between is confirmed by Gemini Flash-Lite. Clusters became coherent, including English/Vietnamese merges.
- Google News sources disabled (kept in `sources.yaml` with the reason); replaced by direct feeds verified from Cloud Run: The Guardian, Al Jazeera, NYT, DW, CNBC, Wired, Engadget. Reuters and AP headlines are no longer available.
- `BUDGET_AMOUNT` in `.env` (set to 520000VND).
- Review fixes: per-run cap of 200 new articles, ingest heartbeat checked by the digest, SIGTERM and startup errors reported, slot windows with one-off ids for manual runs, pending overnight items cleared after the digest, per-item Discord failures isolated, model failures degrade instead of stalling.

## Next steps

- Watch a 7-day run: 14/14 digests, hot alerts within limits, summary accuracy spot checks.
- Upgrade the trial billing account to paid before day 90.
- Tune thresholds in `settings.yaml` after a week of real output.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
