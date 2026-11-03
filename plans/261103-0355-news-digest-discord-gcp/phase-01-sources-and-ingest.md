---
title: "Phase 1: Sources and ingest"
status: todo
---

# Phase 1: Sources and ingest

## Overview

Project skeleton, source fetchers, embeddings, clustering and the Firestore store.
The `ingest` command fetches every source, skips already seen items, embeds new
items and assigns them to event clusters.

## Requirements

- [x] `uv` project, Python 3.12, `src/get_news` package, `python -m get_news ingest|digest [--dry-run]`.
- [x] `sources.yaml` (sources) and `settings.yaml` (topics, thresholds) loaded at start.
- [x] Fetchers: RSS/Atom (feedparser), Google News RSS (publisher from `<source>`),
      Hacker News front page (Algolia), GitHub Trending (HTML).
- [x] Date parsing handles RFC-822, `+07`, and Tuoi Tre `M/D/YYYY h:mm:ss AM` without zone (assume Asia/Ho_Chi_Minh).
- [x] URL canonicalisation (strip tracking params, fragments) and seen-set dedupe in one `state/seen` document.
- [x] Embeddings via `gemini-embedding-001` (768 dims) on the global endpoint.
- [x] Clusters: cosine match against clusters updated in the last 24 h; article list inline in the cluster doc (capped).
- [x] Source health counters in `state/source-health`.

## Implementation Steps

1. Scaffold `pyproject.toml`, `.gitignore`, `.env.example`, config loading.
2. Write fetchers and parsing helpers; save real feed samples as test fixtures.
3. Write the Firestore store with field-owned merge writes (ingest owns article/centroid fields).
4. Write the embedding client and cluster assignment.
5. Wire `run_ingest`.

## Todo

- [x] Scaffold and config
- [x] Fetchers + fixtures + tests
- [x] Store
- [x] Embeddings + clustering + tests
- [x] Ingest job

## Success Criteria

Unit tests for parsing, canonicalisation and clustering pass; a local ingest run
against the real project writes clusters.
