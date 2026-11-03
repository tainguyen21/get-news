---
title: "Phase 3: Hot news and operations alerts"
status: todo
---

# Phase 3: Hot news and operations alerts

## Overview

Hot-news detection runs at the end of each ingest. Operations messages go to `#he-thong`.

## Requirements

- [x] Candidate: ≥3 distinct publishers within 2 h, or Hacker News velocity above the configured threshold.
- [x] Skip candidates similar to anything sent in the last 72 h.
- [x] Flash-Lite importance score; send when ≥8 (slot 3 needs ≥9); ≤3 per Vietnam day.
- [x] 23:00-07:00: mark `hot_pending` instead of sending; the 07:00 digest leads with them.
- [x] Hot message uses the same full summary format, posted to `#tin-nong`.
- [x] Ops: unhandled job error, source failing 3 runs in a row (once per outage),
      digest missing 30 minutes after its slot, Monday 07:00 source-health report.

## Implementation Steps

1. Hot candidate detection and gate (pure functions, tested).
2. Hot send path reusing the digest summary and Discord formatting.
3. Ops notifier and the missed-digest check inside ingest.
4. Weekly health report inside the Monday morning digest.

## Todo

- [x] Hot detection + gate + tests
- [x] Hot send path
- [x] Ops alerts + missed digest check
- [x] Weekly report

## Success Criteria

Gate tests cover caps, slot-3 threshold and quiet hours; a forced error reaches `#he-thong`.
