# News-digest system: fact check (as of 2026-11-02)

Labels used below:
- **VERIFIED**: found in an official, current source.
- **VERIFIED-EMPIRICAL**: confirmed by a live HTTP probe on 2026-11-02 from a residential IP in Asia. The probes did not run from GCP.
- **VERIFIED-SECONDARY**: confirmed by at least two independent reputable secondary sources because the primary source could not be reached.
- **UNVERIFIED**: could not be confirmed; the line says where I looked.

Note: Vertex AI documentation now redirects to `docs.cloud.google.com/gemini-enterprise-agent-platform/...`, and Google brands the product "Gemini Enterprise Agent Platform". The model IDs and the API are unchanged.

## 1. Vertex AI Gemini and embeddings

- **Latest GA Flash is `gemini-3.8-flash`.** It was released 2026-09-02 and retires no earlier than 2027-09-02. Other GA Flash models are `gemini-3.7-flash` (retires 2027-01-28), `gemini-3.6-flash` and `gemini-3.5-flash`. VERIFIED: [3.8 Flash](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-8-flash), [3.7 Flash](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-7-flash), [model versions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions)
- **GA Flash-Lite models are `gemini-3.5-flash-lite` and `gemini-3.1-flash-lite`.** 3.5 Flash-Lite was released 2026-07-21 and 3.1 Flash-Lite on 2026-05-07; each retires no earlier than one year after release. VERIFIED: [3.5 Flash-Lite](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-5-flash-lite), [3.1 Flash-Lite](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-1-flash-lite)
- **`gemini-2.5-flash` and `gemini-2.5-flash-lite` reached their retirement date on 2026-10-20.** The models list still shows them, but the replacement Google names is `gemini-3.8-flash` or `gemini-3.5-flash-lite`. VERIFIED: [model versions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions), [2.5 Flash](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/2-5-flash)
- **Text prices per 1M tokens on the global endpoint (input / output):**
  - 3.8, 3.7 and 3.6 Flash: $0.75 / $3.75 through 2026-12-31, then **$1.50 / $7.50 from 2027-01-01**.
  - 3.5 Flash: $1.50 / $9.00.
  - 3.5 Flash-Lite: $0.30 / $2.50.
  - 3.1 Flash-Lite: $0.25 / $1.50.

  VERIFIED: [pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)
- **Non-global (regional) endpoints cost about 10% more.** For example, 3.8 Flash costs $0.825 / $4.125 on a regional endpoint. VERIFIED: [pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)
- **Flex and batch pricing is 50% of standard.** For example, 3.1 Flash-Lite costs $0.125 / $0.75 that way. VERIFIED: [pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)
- **Reasoning ("thinking") tokens are billed at the output rate.** The price rows read "Text output (response and reasoning)". VERIFIED: [pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)
- **3.8 Flash cannot use the MINIMAL thinking level.** It supports only LOW, MEDIUM (the default) and HIGH. 3.5 Flash-Lite defaults to MINIMAL. VERIFIED: [3.8 Flash](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-8-flash), [3.5 Flash-Lite](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-5-flash-lite)
- **Regions:**
  - 3.8 and 3.7 Flash: global, us and eu only, **not asia-southeast1**.
  - 3.5 Flash: global, us, eu and **asia-southeast1**.
  - 3.5 Flash-Lite: global, us, eu and asia-south1.
  - 3.1 Flash-Lite: global, us and eu.

  VERIFIED: the model pages linked above
- **The global endpoint is supported** at `aiplatform.googleapis.com/.../locations/global/...`. Google says it offers "higher availability" and does not guarantee data residency. VERIFIED: [locations](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/locations)
- **Structured JSON output is supported on all of the Flash and Flash-Lite models above.** Valid JSON is guaranteed only when you set both `response_schema` and `response_mime_type: "application/json"`. JSON mode alone is only a hint. VERIFIED: [structured output](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/control-generated-output)
- **Embedding models:**
  - `gemini-embedding-001` is multilingual, accepts up to 2048 tokens and outputs up to 3072 dimensions. It retires no sooner than 2028-05-20.
  - `gemini-embedding-2` was released GA on 2026-04-22. It accepts up to 8192 tokens and runs on global, us and eu.
  - **`text-multilingual-embedding-002` retires on 2027-04-01.**

  VERIFIED: [text embeddings](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/embeddings/get-text-embeddings), [Embedding 2](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/embedding-2), [model versions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions)
- **Embedding prices:**
  - "Gemini Embedding": $0.00015 per 1,000 "count" online, $0.00012 batch.
  - "Embeddings for Text (excluding Gemini Embedding)", which covers text-multilingual-embedding-002: $0.000025 per 1,000 "count".
  - Gemini Embedding 2 text: $0.20 per 1M tokens online, $0.10 batch. The pricing page labels it "Preview" even though the model page says GA.

  VERIFIED: [pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing). The page does not say whether "count" means tokens or characters, so that part is UNVERIFIED.

## 2. GCP Free Trial

- **The trial gives $300 of credit for 90 days, with no billing during the trial.** VERIFIED: [free features](https://docs.cloud.google.com/free/docs/free-cloud-features)
- **Restrictions during the trial:**
  - No GPUs, Marketplace, quota increases, Windows Server VMs or VMware Engine.
  - Crypto mining is prohibited.
  - The credit cannot pay for the Gemini API in AI Studio or for partner models sold as a service (MaaS).
  - First-party Vertex Gemini is not on that exclusion list.

  VERIFIED: [free features](https://docs.cloud.google.com/free/docs/free-cloud-features)
- **When the trial ends (day 90 or credit used up):**
  - The trial billing account closes, billing is disabled and all resources stop.
  - A 30-day grace period follows; after it, resources are permanently deleted.
  - **To keep things running you must upgrade to a Paid billing account before the trial ends.** Resources then continue without interruption.

  VERIFIED: [free features](https://docs.cloud.google.com/free/docs/free-cloud-features)
- **After upgrading, unused credit stays valid until day 90 and the Free Tier continues.** The Free Tier has no end date, and Google can change it with 30 days' notice. VERIFIED: [free features](https://docs.cloud.google.com/free/docs/free-cloud-features)

## 3. Free tiers (per billing account per month unless noted)

- **Cloud Run Jobs have their own free tier:** 240,000 vCPU-seconds and 450,000 GiB-seconds per month. VERIFIED: [Cloud Run pricing](https://cloud.google.com/run/pricing)
- **Billing rules that shrink that allowance:**
  - Every job instance is billed for its whole lifetime, with a 1-minute minimum.
  - The free tier is applied as a spend discount at Tier 1 prices.
  - **asia-southeast1 (Singapore) is a Tier 2 region**, so the free allowance covers fewer seconds there. asia-southeast3 (Bangkok) is Tier 1.

  VERIFIED: [Cloud Run pricing](https://cloud.google.com/run/pricing)
- **Cloud Run Jobs list price in us-central1:** $0.000018 per vCPU-second and $0.000002 per GiB-second. VERIFIED: [Cloud Run pricing](https://cloud.google.com/run/pricing)
- **Cloud Scheduler gives 3 free jobs per billing account, then $0.10 per job per month.** Paused jobs count. VERIFIED: [Scheduler pricing](https://cloud.google.com/scheduler/pricing)
- **Firestore (Standard edition) free tier:**
  - 1 GiB of storage.
  - 50,000 reads, 20,000 writes and 20,000 deletes per day, resetting around midnight Pacific time.
  - Only one free database per project.

  VERIFIED: [Firestore pricing](https://cloud.google.com/firestore/pricing)
- **Firestore TTL policies are available**, with one TTL field per collection group. Data is "typically deleted within 24 hours" after it expires. **TTL deletes are not covered by the free tier** and need billing enabled; they cost $0.01 per 100k in us-central1. VERIFIED: [TTL docs](https://docs.cloud.google.com/firestore/native/docs/ttl), [Firestore pricing](https://cloud.google.com/firestore/pricing)
- **Secret Manager free tier:** 6 active secret versions and 10,000 access operations per month. Beyond that, access operations cost $0.03 per 10k. The free limits apply during and after the trial. VERIFIED: [Secret Manager pricing](https://cloud.google.com/secret-manager/pricing)
- **Artifact Registry gives 0.5 GB of free storage per month**, shared across all projects on the billing account. VERIFIED: [Artifact Registry pricing](https://cloud.google.com/artifact-registry/pricing)
- **Cloud Logging gives the first 50 GiB of logs per project per month free**, then $0.50 per GiB. VERIFIED: [Observability pricing](https://cloud.google.com/products/observability/pricing)

## 4. Discord webhooks

- **A message can carry up to 10 embeds**, for both webhook execute and message create. VERIFIED: [webhook](https://docs.discord.com/developers/resources/webhook), [message](https://docs.discord.com/developers/resources/message)
- **Embed limits:**
  - Description: 4096 characters.
  - Title: 256 characters.
  - Up to 25 fields; field value 1024 characters.
  - Footer: 2048 characters.

  VERIFIED: [message, Embed Limits](https://docs.discord.com/developers/resources/message)
- **All title, description, field, footer and author text across all embeds in one message must total 6000 characters or less.** Going over returns 400. VERIFIED: [message](https://docs.discord.com/developers/resources/message)
- **Message `content` is limited to 2000 characters.** VERIFIED: [message](https://docs.discord.com/developers/resources/message)
- **Embed images can use an external URL.** The `image.url` field "only supports http(s) and attachments". Discord also deduplicates embeds by URL, so if several embeds share a URL only the first is shown. VERIFIED: [message](https://docs.discord.com/developers/resources/message)
- **Official rate-limit rules:**
  - Per-route limits are dynamic, and Discord says not to hard-code them; read the `X-RateLimit-*` headers and `retry_after` instead.
  - The global limit is 50 requests per second, applied per IP when no auth header is sent.
  - Too many 401/403/429 responses (10,000 per 10 minutes) trigger a temporary ban.

  VERIFIED: [rate limits](https://docs.discord.com/developers/topics/rate-limits)
- **Per-webhook numbers such as "5 requests per 2 seconds" or "30 messages per minute per channel" come only from community guides.** UNVERIFIED: they are not in Discord's docs ([Hookdeck guide](https://hookdeck.com/webhooks/platforms/guide-to-discord-webhooks-features-and-best-practices)).

## 5. News sources

- **NewsAPI.org free (Developer) plan:**
  - **Articles have a 24-hour delay.**
  - 100 requests per day; search covers up to 1 month back.
  - **"Development and testing in a development environment only … cannot be used in staging or production (including internally)."**

  VERIFIED: [NewsAPI pricing](https://newsapi.org/pricing)
- **GNews.io free plan:**
  - 100 requests per day, 10 articles per request.
  - **12-hour delay**, 30 days of history.
  - Personal and non-commercial use only.

  VERIFIED: [GNews pricing](https://gnews.io/pricing)
- **Google News RSS (topic and search feeds) works.** Top headlines and `rss/search?q=...when:1h` both return 200 with up to 100 items, and `site:reuters.com` and `site:apnews.com` queries also return items. VERIFIED-EMPIRICAL
- **Google News RSS item links are opaque redirects** (`news.google.com/rss/articles/CBMi...`). Since 2024 they are no longer base64 publisher URLs. VERIFIED-EMPIRICAL, plus [googlenewsdecoder README](https://github.com/SSujitX/google-news-url-decoder)
- **The usual 2026 way to resolve them is the `googlenewsdecoder` package** (v0.2.2, 2026-10-18). It fetches a signature for each article and then sends one `batchexecute` POST. Google may answer with HTTP 429, so the package offers interval and proxy settings. VERIFIED: [PyPI](https://pypi.org/project/googlenewsdecoder/), [README](https://github.com/SSujitX/google-news-url-decoder)
- **The official Hacker News Firebase API (v0) is live** and its README says "There is currently no rate limit". VERIFIED: [HN API](https://github.com/HackerNews/API), plus a live 200 response
- **The Algolia HN Search API is live**, and its docs limit each IP to 10,000 requests per hour. VERIFIED: [hn.algolia.com/api](https://hn.algolia.com/api) (text from the page's JS bundle), plus a live 200 response. Algolia's `hn-search` repo is archived, but the service still runs.
- **Reddit shut down unauthenticated `.json` endpoints**, announced in r/modnews on 2026-05-28; these requests now return 403. VERIFIED-SECONDARY: [Open RSS](https://openrss.org/blog/go-easy-on-the-feeds-reddit), [dev.to](https://dev.to/tonywangca/why-reddit-blocked-unauthenticated-json-in-2026-and-how-to-still-get-reddit-data-58b9)
- **Reddit RSS ends 2026-11-13, and Reddit says there is no replacement outside communities you moderate.** VERIFIED-SECONDARY: [TechCrunch 2026-09-30](https://techcrunch.com/?p=3172243), [Decrypt](https://decrypt.co/379892/reddit-killing-rss-feeds-and-public-api-access-to-fight-ai-scrapers), [mjtsai](https://mjtsai.com/blog/2026/10/06/reddit-to-remove-rss/)
- **Reddit is closing its public Data API in stages:**
  - 2026-10-31: **new access requests closed** (already past).
  - 2027-01-12: unregistered apps start losing access.
  - March 2027: all public API access ends.
  - After that the paths are migration to Devvit or a paid licence.

  The primary posts are r/redditdev `1wubcvf` and r/modnews `1wubgvt`. VERIFIED-SECONDARY: the same three sources
- **Probe of Reddit RSS:** `old.reddit.com/r/worldnews/.rss` returned 302 to `/login/?reason=lor2`. VERIFIED-EMPIRICAL. `www.reddit.com` could not be tested because it resolves to 127.0.0.1 on this machine (a local hosts block). That test and the primary posts themselves are UNVERIFIED.
- **GitHub Trending has no official API.** It is an HTML page, and people scrape `github.com/trending`, which returned 200. VERIFIED-SECONDARY: [dev.to guide](https://dev.to/agenthustler/how-to-scrape-github-in-2026-profiles-repos-and-trending-complete-guide-4p00) and Apify scraper listings, plus the empirical probe

## 6. Full-text extraction

- **trafilatura is actively maintained.** The latest release is 2.3.1 (2026-10-06, Python ≥3.10), and the last commit was 2026-10-30. VERIFIED: [PyPI](https://pypi.org/project/trafilatura/), [GitHub](https://github.com/adbar/trafilatura)
- **Reuters:**
  - It has no public RSS feed (discontinued in 2020); the old outbound feed URL returns 404.
  - The site returns **401 with a DataDome JS challenge**, even from a residential IP.

  VERIFIED-EMPIRICAL, plus [feeder.co](https://feeder.co/knowledge-base/rss-content/reuters-rss-feeds/)
- **AP:**
  - `apnews.com` pages and `.rss` URLs return **403 with a Cloudflare "Just a moment…" challenge**, even from a residential IP.
  - AP has no working public RSS feed.

  VERIFIED-EMPIRICAL, plus [feeder.co](https://feeder.co/knowledge-base/rss-content/ap-news-rss-feeds/)
- **BBC:** `feeds.bbci.co.uk` feeds return 200, and a `bbc.co.uk/news/articles/...` page returned 200 with full HTML. The feeds carry only about 100-character descriptions, not full text. VERIFIED-EMPIRICAL
- **The Verge:**
  - It has run a metered paywall since 2024-12.
  - The test article was marked `"isAccessibleForFree":false`.
  - The RSS feed has 10 entries with partial content (median about 730 characters).
  - Full text may be truncated for non-subscribers.

  VERIFIED-EMPIRICAL, plus [Semafor](https://www.semafor.com/article/12/03/2024/the-verge-raises-a-partial-paywall-its-a-tragedy-that-garbage-is-free-and-news-is-behind-paywalls) and [Daring Fireball](https://daringfireball.net/linked/2024/12/03/the-verge-launches-a-subscription)
- **Extra finding for Ars Technica:** article pages return **405 with an AWS WAF captcha** to non-browser clients. The feed carries partial content (median about 1,150 characters). TechCrunch article pages returned 200, though its feed has about 100-character descriptions only. VERIFIED-EMPIRICAL
- **How these sites behave from GCP datacenter IPs is UNVERIFIED.** I did not probe from GCP. Secondary sources say DataDome blanket-blocks datacenter ranges, so expect results no better than above.

## 7. Vietnamese RSS (all live on 2026-11-02 with same-day items; VERIFIED-EMPIRICAL)

- **VnExpress** (index: https://vnexpress.net/rss):
  - https://vnexpress.net/rss/tin-moi-nhat.rss (47 items)
  - https://vnexpress.net/rss/the-gioi.rss (60)
  - https://vnexpress.net/rss/khoa-hoc-cong-nghe.rss (60)
  - https://vnexpress.net/rss/so-hoa.rss (60)
  - Dates are standard RFC-822 with `+0700`.
- **Tuoi Tre** (index: https://tuoitre.vn/rss.htm), 50 items each:
  - https://tuoitre.vn/rss/tin-moi-nhat.rss
  - https://tuoitre.vn/rss/the-gioi.rss
  - https://tuoitre.vn/rss/cong-nghe.rss
  - https://tuoitre.vn/rss/nhip-song-so.rss
  - https://tuoitre.vn/rss/home.rss
  - **`pubDate` is not standard**: for example `11/2/2026 9:17:00 PM`, with a U+202F narrow no-break space and no timezone.
- **Genk:**
  - https://genk.vn/rss/home.rss (61 items)
  - https://genk.vn/rss/ai.rss, /rss/mobile.rss and /rss/internet.rss (all 200)
  - `pubDate` uses a non-standard timezone, `+07`.
  - The index page https://genk.vn/rss.chn links only `index.rss`, which returns HTML, not a feed.

## Facts that change a design choice

1. **Reddit cannot be a source as planned.** Unauthenticated `.json` already returns 403, RSS ends 2026-11-13, and new public API access closed on 2026-10-31. Drop r/technology and r/worldnews, or accept a paid or third-party route.
2. **Neither NewsAPI nor GNews free tiers can supply hot news.** NewsAPI is delayed 24 hours and limited to development; GNews is delayed 12 hours. The workable free "aggregator" is Google News RSS (search with `when:1h` or `site:` queries, or topic feeds). It needs a link-decoding step that makes extra HTTP calls and risks 429 responses.
3. **Reuters and AP have no RSS and block direct fetching** (DataDome 401, Cloudflare 403). Get their headlines through Google News `site:` queries. Expect no full text for them, and build summaries from the other articles in the same cluster.
4. **Full text needs page fetching because feeds carry only snippets.** The Verge is paywalled, and Ars returns a WAF captcha to scripts. Design summaries to tolerate partial text.
5. **Do not use Gemini 2.5 models; they retired 2026-10-20.** `gemini-3.8-flash` does not run in asia-southeast1, so call it through the **global endpoint**, which is also about 10% cheaper.
6. **3.8 Flash doubles in price on 2027-01-01**, to $1.50 / $7.50 per 1M tokens. For budgeting, 3.1 Flash-Lite ($0.25 / $1.50) is the cheapest GA option for scoring.
7. **Keep thinking tokens under control.** They bill at the output rate, and 3.8 Flash's lowest setting is LOW.
8. **Use `gemini-embedding-001` (or `gemini-embedding-2`) for embeddings, not `text-multilingual-embedding-002`**, which retires 2027-04-01.
9. **Ingest every 15 minutes may use most of the Cloud Run Jobs free vCPU allowance.** That is 96 runs a day, about 2,976 runs a month, each billed at least 60 seconds. At 1 vCPU that is at least about 178,560 vCPU-seconds against 240,000 free. Because asia-southeast1 is Tier 2, the free tier covers fewer seconds there. Size CPU small, or pick a Tier 1 region such as asia-southeast3.
10. **Scheduling stays free with two jobs.** Use one ingest job and one digest job with cron `0 7,19 * * *`, which stays within the 3 free jobs.
11. **Firestore TTL is cheap but not free.** TTL deletes need billing and run within about 24 hours, so do not rely on TTL for exact dedupe windows.
12. **Each Discord digest will take several webhook posts.** One message allows only 6000 characters across all embeds, so at most one full-length summary (4096 characters) fits per message. Pace the posts from the rate-limit headers.
13. **The trial has a hard stop.** Upgrade to a Paid billing account before day 90, or all jobs stop and are deleted 30 days later. The Free Tier continues after the upgrade.
14. **Tuoi Tre and Genk dates need custom parsing.** Assume Asia/Ho_Chi_Minh when a date has no timezone.

## Limitations / unresolved

- I did not probe from a GCP IP, so blocking behaviour of news sites against Cloud Run egress is untested.
- The pricing page says embedding prices are "per 1,000 count" but does not say whether that means tokens or characters.
- I could not read the primary Reddit posts (reddit.com is unreachable from this machine), so the Reddit dates rest on TechCrunch, Decrypt and mjtsai.
- Discord per-webhook rate numbers are undocumented.
- I did not check whether Cloud Run Jobs, Firestore and Scheduler are all offered in asia-southeast3.
