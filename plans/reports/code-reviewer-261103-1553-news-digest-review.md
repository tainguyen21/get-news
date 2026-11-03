# Code review: get-news (personal news digest on GCP)

Date: 2026-11-03. Scope: `src/get_news/*.py` (~1,560 LOC), `settings.yaml`, `sources.yaml`,
`deploy.sh`, `Dockerfile`, ignore files, `tests/`. `uv run pytest -q`: 37 passed. No linter or
type checker is configured; coverage was not measured.

## Overall

The design is implemented with care in several places:

- Each job writes only its own fields, as merges.
- Hot-alert counters and flags are written in one atomic batch.
- Webhook URLs are redacted from logs and alerts, and Discord mentions are disabled.
- `.env` is excluded from both the Cloud Build upload and the Docker build context.

The serious risks are in the orchestration code (`jobs.py`), and none of it is tested:

- An ingest run saves nothing unless the whole run finishes, under a 10-minute timeout.
- Some failures send no alert at all.
- How the digest slot is derived lets a manual run swallow a scheduled digest.
- The `hot_pending` flag is not always cleared.

Findings below are ranked. Wherever this report says "Reproduced", the scenario was run
against the real code.

## High

### H1. Ingest saves only at the end and has a 10-minute timeout, so a cold start or backlog can fail forever with no alert
- **Evidence:**
  - `jobs.py:106-115`: embed, then assign, then `save_clusters` and `save_seen` only after everything.
  - `clustering.py:53-54` with `jobs.py:48-51`: one Flash-Lite `same_event` call, one at a time, for each article whose best match falls between 0.66 and 0.88.
  - `deploy.sh:84`: `--task-timeout=10m --max-retries=0`.
  - `__main__.py:43-53`: an alert is sent only when Python raises an exception.
- **Failure scenario:**
  1. The first live run (Phase 4 step 3) finds roughly 750-800 articles inside 48h. This is estimated from the fixtures: about 50-70 items per Google News, Tuổi Trẻ and VnExpress feed, and up to 100 each from Reuters and AP.
  2. Once a few hundred clusters exist, many articles have some cluster at 0.66 or above. That means hundreds of model calls in sequence.
  3. If the run passes 10 minutes, Cloud Run stops the task. No Python exception is raised, so no ops alert is sent.
  4. Nothing was saved, so every later run starts from the same backlog and is stopped the same way.
  5. `check_missed_digests` also runs inside ingest, so it never fires.

  The same thing happens after any outage longer than about a day.
- **Fix:**
  - Cap the work per run: process the newest ~150 fresh articles and leave the rest unseen for the next run. Alternatively, save clusters and seen in chunks.
  - Run the `confirm` calls concurrently.
  - Add a SIGTERM handler that raises an exception so the existing alert path runs.
  - Add a Cloud Monitoring alert on failed job executions.

### H2. Startup and config errors send no alert, and the missed-digest check lives inside the failing job
- **Evidence:**
  - `__main__.py:30-42`: `load_config`, `clients()` and `Context` are created outside the `try`.
  - `config.py:61`: `Source(**item)` raises `TypeError` on any misspelled key.
  - `jobs.py:125`: the missed-digest check runs inside ingest.
  - `deploy.sh` checks nothing before building.
  - `docs/setup-and-operations.md:63` tells the user to "Edit sources.yaml / settings.yaml, then ./deploy.sh".
- **Failure scenario:** a YAML typo, or `enable: false` written instead of `enabled`, gets deployed. Both jobs crash before the `try`, so nothing reaches Discord. Ingest is down, so no missed-digest alert either. Delivery stops completely and silently.
- **Fix:**
  - Build the ops `Webhook` from the environment first, then wrap all of `main()` in the `try`.
  - In `deploy.sh`, run `uv run pytest -q` and a `load_settings()` / `load_sources()` check before `builds submit`.
  - Add a Cloud Monitoring alert policy on `run.googleapis.com/job/completed_execution_count` with `result=failed`, as a backstop outside the app.

### H3. A manual or off-schedule digest run uses up the next scheduled slot
- **Evidence:**
  - `jobs.py:220-224`: the slot is `am` if the hour is before 12, otherwise `pm`; status `done` then makes later runs skip.
  - `docs/setup-and-operations.md:64`: "Run a job now: gcloud run jobs execute get-news-digest".
  - `phase-04-deploy-and-verify.md:25`: the plan's own verification step does exactly this.
- **Failure scenario:**
  1. A test run at 16:00 today writes `digests/2026-11-03-pm` with status `done`.
  2. The 19:00 scheduled run logs "already sent" and exits.
  3. `check_missed_digests` sees `done`, so no alert.
  4. The next 07:00 window starts at 19:00, so clusters last updated between 16:00 and 19:00 are never considered.
- **Fix:** tie a run to a slot only when local time is within, say, `[slot, slot+90m)`. Otherwise use `{date}-manual-{HHMM}`, or require a `--slot` argument. Document this.

### H4. `hot_pending` is never cleared on clusters that are not sent, so duplicates resurface days later as overnight hot news
- **Evidence:**
  - `jobs.py:161-179`: `hot_pending` is set after a repeat check against sent clusters only, not against other pending ones.
  - `store.py:59-60`: the `hot_pending == True` query has no time bound.
  - `jobs.py:229,245`: pending clusters join every digest pool and skip `min_material_chars`.
  - `ranking.py:62-64`: a rejected cluster keeps its flag.
  - Only `store.py:92` and `store.py:111` clear the flag, and only on send.
- **Reproduced:**
  1. Overnight clusters A and B describe the same event. Both are marked pending.
  2. The 07:00 digest selects A and rejects B as a repeat. B stays pending.
  3. At 19:00, B is rejected again because it matches the sent cluster A.
  4. Once A leaves the 72h lookback, `select()` returns B. B is posted first under "TIN NÓNG QUA ĐÊM", 3+ days late. The cluster TTL is `updated_at` + 7 days, so B is still there.

  The same happens to a pending cluster that is rescored to `skip`, or whose summary failed. The second case is re-labelled as overnight news at 19:00.
- **Fix:**
  - When a digest succeeds, clear `hot_pending` on every pending cluster in the pool that was not sent.
  - Put a time bound on pending clusters: store `hot_pending_at` and only consider clusters set since the last `quiet_start`.
  - In `process_hot`, include already-pending clusters in the repeat set.

## Medium

### M1. A hot alert and the digest can both deliver the same event at 07:00 and 19:00
- **Evidence:**
  - `deploy.sh:100-101`: the `*/15` ingest schedule fires together with `0 7,19`.
  - `jobs.py:161` reads `c.sent` from data loaded at the start of ingest.
  - `ranking.py:27` skips `other.id == cluster.id`. So `jobs.py:166` and `jobs.py:175` cannot see that this same cluster was just sent. Reproduced: `is_repeat(X, [X])` returns `False`.
  - The reverse also happens: the digest's `sent` list (`jobs.py:230`) is loaded before a concurrent hot alert.
- **Failure scenario:**
  1. The 19:00 digest selects cluster X.
  2. The 19:00 ingest sees X reach 3 publishers and sends a hot alert at about 19:01.
  3. The digest posts X at about 19:04.

  The event appears in both channels, and one of the day's hot slots is used up.
- **Fix:**
  - In `process_hot`, build `sent_ids = {s.id for s in sent}` and skip those ids.
  - In both paths, re-read the cluster document right before sending, or claim it in a transaction (for example, set a claim field only if it is absent).
  - Optionally, defer hot alerts while today's digest document has status `started`.

### M2. Hacker News point updates do not bring a story into the digest or trigger a rescore
- **Evidence:**
  - `jobs.py:128-135` marks the cluster `touched` but leaves `updated_at` unchanged.
  - The digest pool is selected by `updated_at` (`jobs.py:228`, `store.py:56-57`).
  - A rescore happens only after 2 more publishers (`jobs.py:64`).
- **Failure scenario:**
  - A story first seen at 05:00 with 40 points has 900 points by 18:00. The 19:00 window starts at 07:00, so the story is excluded. It is also too old for the 6-hour hot rule.
  - A cluster scored at 07:00 with low points keeps that importance when it later becomes a fast-rising HN candidate. `jobs.py:167` does not rescore it, so the hot gate uses a stale score.
- **Fix:**
  - When `hn_points` rises a lot, bump `updated_at`, or a separate `active_at` field that the digest query uses.
  - Store `scored_hn_points` and rescore when points have at least doubled.

### M3. One repeatable model failure blocks ingest forever; a scoring failure kills the whole digest
- **Evidence:**
  - `llm.py:186`, called through `jobs.py:48-51`: `json.loads(response.text)` raises when the response is empty, blocked or truncated.
  - Articles are marked seen only after the whole batch (`jobs.py:110-115`).
  - `llm.py:164` and `jobs.py:234`: no fallback when scoring fails.
- **Failure scenario:** one headline makes `same_event` return no text. At temperature 0 this repeats on every run, so the run raises `TypeError` every time. No new clusters are created, and an ops alert goes out every 15 minutes (`__main__.py:50` has no deduplication).
- **Fix:**
  - In `confirm`, catch exceptions and treat them as "no match"; count them and alert once.
  - If scoring fails, leave the clusters unscored and fall back to `prerank` plus `category_hint`.
  - Deduplicate repeated ops alerts.

### M4. One Discord 4xx response stops the rest of the digest, and the retry hits the same item
- **Evidence:**
  - `discord.py:50-52` raises on any 4xx.
  - `jobs.py:262-271` has no per-item error handling.
  - `httpx` transport errors and timeouts are never retried (`discord.py:43`).
- **Failure scenario:** Discord rejects one embed with a 400. The job fails. The retry selects the same unsent item again and fails again, so nothing after that item is delivered.
- **Fix:**
  - Per item, catch a `DiscordError` with status 400: log it, send an ops alert, and continue. Keep 401 and 404 fatal.
  - Retry `httpx.TransportError` the same way as 5xx responses.

### M5. Firestore reads probably exceed the 50k/day free tier, and grow with the number of sources
- **Evidence:**
  - `jobs.py:92` calls `store.py:56-57`, which reads every cluster updated in the last 24h as a full document, every 15 minutes (96 runs a day).
  - In addition, whenever there is a hot candidate (most runs, because of HN), `clusters_sent_since` runs 2 queries returning about 70 documents.
- **Estimate:**
  - About 800-1,000 new articles a day gives about 600-900 clusters in any 24h window.
  - That is roughly 60k-95k reads a day before any digest reads.
  - The cost is cents a day. But `docs/setup-and-operations.md:90` claims free or near-free, and adding sources is a documented routine change.
- **Fix:**
  - Keep a compact `state/centroids` document (id, float16 centroid, `updated_at`, sent flags), written alongside `state/seen`.
  - Load full cluster documents only for clusters that were matched or touched. Alternatively, reduce `match_window_hours`.

### M6. Full-text fetching has no limit on download size or number of attempts, on URLs from outside
- **Evidence:**
  - Download size: `fulltext.py:31-34` reads the whole response body. There is no size cap and no content-type check. HN links can be PDFs or large binaries, and the 20s timeout applies to each operation, not the whole download.
  - Repeated attempts: `fulltext.py:54-73` adds a domain to `used_domains` only on success, so a failing domain is retried for each of its articles. A cluster can hold up to 20 articles, each needing a Google News decode and a fetch.
  - No overall limit: `jobs.py:243-247` runs this one candidate at a time, under the 20-minute task timeout.
- **Fix:**
  - Stream the response with a byte cap of about 2-3 MB, and require `text/html`.
  - Remember failed domains and cap attempts per cluster at about 5.
  - Give the whole selection step a wall-clock budget.

  Requests to the metadata server are not a risk: it requires the `Metadata-Flavor` header, which these fetches do not send.

## Low

- **L1. A rerun can post more than 10 items.**
  - `jobs.py:236-240` with `ranking.py:49`: the total is the sum of each section's remaining quota.
  - It ignores extra items already sent through the spare-slot rule. Reproduced: after 6 tech items were sent, the rerun picks 5 more, for 11 in total.
  - Fix: compute the total as `tech_items + world_items - sum(already)`.
- **L2. A missing webhook URL on a real (non-dry) run is printed instead of sent, and the digest still marks the items sent** (`discord.py:39`, `jobs.py:270-271`).
  - Fix: raise when the URL is missing and this is not a dry run.
- **L3. Dry runs change stored state.**
  - `score()` saves scores (`jobs.py:72`).
  - An ingest dry run consumes `seen`, so a hot alert that was only printed is never sent.
- **L4. The schedule can drift from the settings.**
  - The cron is hard-coded in `deploy.sh:101`.
  - The missed-digest check uses `settings.digest.slots` (`jobs.py:199`), and the docs (`docs/setup-and-operations.md:22`) say slots can be tuned in `settings.yaml`.
  - Fix: derive the cron from the settings, or document that both must change together.
- **L5. GitHub Trending items and undated items come back as new every 72h.**
  - GitHub Trending sets `published_at=now` (`sources.py:171`); undated items fall back to now (`sources.py:59`).
  - When the seen entry is pruned (`jobs.py:90-91`), they are ingested again.
  - A repo that keeps trending can be delivered again after the 72h repeat window.
- **L6. `redact()` only matches the plain webhook URL form** (`textutil.py:16`).
  - It does not match `/api/v10/webhooks/...` or a malformed secret.
  - Fix: also replace the configured webhook values themselves.
- **L7. `is_repeat` runs twice per hot candidate** (`jobs.py:166` and `jobs.py:175`).
  - This doubles the same-event model calls on every run for long-lived HN candidates.
- **L8. Changing `models.embedding` or `embedding_dims` breaks matching.**
  - `np.stack` fails for about 24h (`clustering.py:31`).
  - Repeat checks silently compare vectors from different models for 72h.
  - Fix: store the model and dims on each cluster and filter out mismatches.
- **L9. A persistent failure sends an ops alert every 15 minutes** (`__main__.py:50`).
  - Fix: deduplicate through a state document (alert on the first failure and on recovery).

## Checked and found OK

- **Git Bash:**
  - `$(...)` strips CR from Windows programs' output, and `grep -qx` matches; both tested in this shell. So `PROJECT_NUMBER`, `BILLING` and the budget check work.
  - No gcloud argument starts with `/`, so Git Bash's path conversion does not alter any of them.
- **Secrets:**
  - Secret values reach gcloud through stdin and are never echoed.
  - `.env` is excluded by `.gcloudignore`, `.dockerignore` and `.gitignore`.
  - `DiscordError` never includes the URL.
  - The `httpx` request log is set to WARNING.
  - Tracebacks are redacted before logging and alerting.
- **Firestore writes:**
  - Fields written by ingest and fields written by scoring/delivery never overlap, and every write is a merge.
  - `mark_hot_sent` updates the counter and the cluster flag in one atomic batch.
  - Writes total about 3-5k a day, under the 20k free tier; HN point refreshes (~25 documents a run) are most of it.
- **`state/seen` size:** about 25 bytes per entry compressed, so roughly 40k entries fit under 1 MiB; 3-6k are expected.
- **Feed dates:** Genk `+07`, Tuổi Trẻ times with no zone, and VnExpress all convert to the correct UTC against the fixtures.
- **Config path:** `CONFIG_DIR` resolves to `/app` in the image, because `uv sync` installs the project in editable mode.

## Test gaps

`jobs.py` (ingest, `process_hot`, digest, missed-digest check) and `store.py` have no tests, and every High and Medium finding is in that code. Add fakes for Store, Gemini and Webhook, then cover:

- a digest rerun after a crash: no duplicates, quota respected;
- the full `hot_pending` lifecycle;
- an off-schedule digest run;
- the hot daily cap, quiet hours, and a cluster that was sent during the run;
- the missed-digest time window.

## Recommended order

1. H1, before the Phase 4 live run.
2. H3, before any manual verification.
3. H2.
4. H4.
5. M1, M3, M4.
6. The rest.

## Unresolved questions

- Should overnight `hot_pending` items count against the 5 tech / 5 world quotas? Currently they do.
- Should major new developments on an event that was already sent ever be delivered again? Currently, new articles that join a sent cluster are suppressed permanently.
