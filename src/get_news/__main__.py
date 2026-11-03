"""Command line entry: python -m get_news {ingest|digest} [--dry-run]."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import traceback

from get_news import jobs
from get_news.config import load_config
from get_news.discord import Webhook
from get_news.gcp import clients
from get_news.llm import Gemini
from get_news.sources import http_client
from get_news.store import Store
from get_news.textutil import redact

log = logging.getLogger("get_news")
REQUIRED_WEBHOOKS = {"ingest": ("hot", "ops"), "digest": ("digest", "ops")}


class JobTerminated(RuntimeError):
    """SIGTERM from Cloud Run, sent when the task timeout is reached."""


def _terminate(signum, frame):
    raise JobTerminated("job stopped by SIGTERM (task timeout or shutdown)")


def run(job: str, dry_run: bool, http, ops_hook: Webhook) -> None:
    cfg = load_config()
    missing = [name for name in REQUIRED_WEBHOOKS[job] if not getattr(cfg.webhooks, name)]
    if missing and not dry_run:
        raise RuntimeError(f"missing Discord webhook settings: {', '.join(missing)}")
    genai_client, db = clients(cfg)
    ctx = jobs.Context(
        cfg=cfg,
        store=Store(db),
        gemini=Gemini(genai_client, cfg.settings),
        http=http,
        dry_run=dry_run,
        digest_hook=Webhook(cfg.webhooks.digest, http, "Bản tin", dry_run),
        hot_hook=Webhook(cfg.webhooks.hot, http, "Tin nóng", dry_run),
        ops_hook=ops_hook,
    )
    jobs.run_ingest(ctx) if job == "ingest" else jobs.run_digest(ctx)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="get_news", description="Personal news digest jobs")
    parser.add_argument("job", choices=["ingest", "digest"])
    parser.add_argument("--dry-run", action="store_true", help="print Discord messages instead of sending; record nothing as sent")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", stream=sys.stdout)
    for noisy in ("httpx", "google_genai", "trafilatura", "googlenewsdecoder"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Created before anything that can fail, so configuration and startup errors are reported too.
    http = http_client()
    ops_hook = Webhook(os.environ.get("DISCORD_WEBHOOK_OPS") or None, http, "Hệ thống", args.dry_run)
    signal.signal(signal.SIGTERM, _terminate)
    try:
        run(args.job, args.dry_run, http, ops_hook)
    except Exception as exc:
        message = redact(f"{type(exc).__name__}: {exc}")[:1500]
        log.error("job %s failed\n%s", args.job, redact("".join(traceback.format_exception(exc))))
        try:
            ops_hook.send_text(f"❌ **Job `{args.job}` lỗi**\n```\n{message}\n```")
        except Exception as notify_exc:
            log.error("ops alert failed: %s", redact(str(notify_exc)))
        sys.exit(1)


if __name__ == "__main__":
    main()
