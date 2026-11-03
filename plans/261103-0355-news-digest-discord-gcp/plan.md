---
title: "news-digest-discord-gcp"
description: "Personal tech + world news digest in Vietnamese, delivered to Discord, running on GCP Cloud Run Jobs"
status: in-progress
priority: P1
effort: "3-4 days"
tags: [python, gcp, cloud-run-jobs, firestore, vertex-ai, discord]
created: 2026-11-03
---

# news-digest-discord-gcp

## Overview

Python 3.12 system on a new GCP project (us-central1). Two Cloud Run Jobs from one
image: `ingest` (every 15 min: fetch sources, dedupe, embed, cluster, hot-news gate)
and `digest` (07:00 and 19:00 Asia/Ho_Chi_Minh: rank, fetch full text, summarize in
Vietnamese, post to Discord). Firestore holds clusters and sent history; Secret
Manager holds three Discord webhook URLs. Accepted advice:
`plans/reports/advise-261102-1053-news-discord-gcp-preview.html`, facts:
`plans/reports/researcher-261102-2246-news-system-facts.md`.

## Done means

- Redeployable with one `deploy.sh`.
- Digest: ~5 tech + ~5 world items, one Discord message per item (title, bold lead,
  all main points as bullets, original image, sources, link); no repeated event inside
  or across digests.
- Hot news: ≤3/day, none 23:00-07:00 (overnight items lead the 07:00 digest), not
  repeated in digests.
- `#he-thong` receives job errors, repeatedly failing sources, missed digests, and a
  Monday source-health report.
- Sources configured in `sources.yaml`; budget alerts at $10/$20.

## Out of scope

Interactive bot or commands, DM, AI images, web UI, multi-user, 👍/👎 learning,
long-term archive, Reddit, NewsAPI/GNews, bypassing Reuters/AP bot protection.

## Constraints

GCP only; ≤ $20/month; Gemini via Vertex AI global endpoint (3.1 Flash-Lite for
scoring, 3.8 Flash with thinking LOW for summaries, gemini-embedding-001); LLM calls
per selected cluster only; webhook URLs only in Secret Manager / local `.env`.

## Phases

| # | Phase | Status |
|---|-------|--------|
| 1 | [Sources and ingest](./phase-01-sources-and-ingest.md) | Completed |
| 2 | [Digest, summaries and Discord](./phase-02-digest-summaries-discord.md) | Completed |
| 3 | [Hot news and operations alerts](./phase-03-hot-news-and-ops.md) | Completed |
| 4 | [Deploy and live verification](./phase-04-deploy-and-verify.md) | Completed |

Phases run in order; each depends on the previous one.

## Success Criteria

- [x] Unit tests pass (`uv run pytest`).
- [x] A live ingest run on GCP stores clusters from all configured sources.
- [x] A live digest run posts a correctly formatted digest to `#tin-tuc`.
- [x] A forced failure posts to `#he-thong`.
- [x] Scheduler jobs exist with the Asia/Ho_Chi_Minh time zone.
- [ ] 7-day run (14/14 digests) — verified by the user after delivery.

<!-- slug: news-digest-discord-gcp -->
