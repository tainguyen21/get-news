"""Google Cloud clients. Cloud Run uses its service account through default credentials.

For local runs with GET_NEWS_GCLOUD_AUTH=1, the active gcloud user's access token is used
instead of application-default credentials (which may belong to another account).
"""

from __future__ import annotations

import os
import shutil
import subprocess

from google import genai
from google.genai import types
from google.cloud import firestore
from google.oauth2.credentials import Credentials

from get_news.config import Config


def _credentials() -> Credentials | None:
    if os.environ.get("GET_NEWS_GCLOUD_AUTH") != "1":
        return None
    gcloud = shutil.which("gcloud")
    if not gcloud:
        raise RuntimeError("GET_NEWS_GCLOUD_AUTH=1 needs the gcloud CLI on PATH")
    token = subprocess.run([gcloud, "auth", "print-access-token"], capture_output=True, text=True, check=True)
    return Credentials(token.stdout.strip())


def clients(cfg: Config) -> tuple[genai.Client, firestore.Client]:
    credentials = _credentials()
    genai_client = genai.Client(
        vertexai=True,
        project=cfg.project,
        location=cfg.location,
        credentials=credentials,
        http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=4)),
    )
    db = firestore.Client(project=cfg.project, credentials=credentials)
    return genai_client, db
