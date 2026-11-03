---
title: "Phase 2: Digest, summaries and Discord"
status: todo
---

# Phase 2: Digest, summaries and Discord

## Overview

The `digest` command selects ~5 tech + ~5 world events from the last 12 hours, gathers
full text for the selected events only, writes complete Vietnamese summaries and posts
one Discord message per item.

## Requirements

- [x] Candidate pool: clusters updated in the last 12 h plus overnight hot items, excluding
      clusters sent (or similar to clusters sent) in the last 72 h.
- [x] Heuristic pre-rank (distinct publishers, HN velocity, Techmeme, recency), then one
      Flash-Lite batch call for importance, category (`tech` / `world` / `skip`) and topic priority.
- [x] Full text with trafilatura for up to 3 readable articles per event; skip blocked
      domains; decode Google News links only for selected items; thin events yield to the next candidate.
- [x] Flash summary with response schema: Vietnamese title, bold lead, all main points
      (no fixed count), discrepancy note when sources disagree; facts only from given text.
- [x] Discord: header message, section messages, one embed per item, `?wait=true`,
      rate-limit headers honoured, per-item sent markers so a rerun never double-posts.

## Implementation Steps

1. Ranking and selection.
2. Full-text gathering and image choice.
3. Gemini scoring and summary calls.
4. Discord webhook client and embed formatting.
5. Wire `run_digest` with the `digests/{date}-{am|pm}` idempotency document.

## Todo

- [x] Ranking + tests
- [x] Full text + image
- [x] Gemini scoring and summary
- [x] Discord client + tests
- [x] Digest job

## Success Criteria

Unit tests for ranking, embed limits and rate-limit handling pass; a dry-run digest
prints well-formed payloads from real data.
