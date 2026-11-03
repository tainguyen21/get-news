---
title: "Phase 4: Deploy and live verification"
status: todo
---

# Phase 4: Deploy and live verification

## Overview

Container image, one idempotent `deploy.sh`, a new GCP project, and live runs.

## Requirements

- [x] `Dockerfile` (python:3.12-slim, uv sync from lockfile) and `.dockerignore`.
- [x] `deploy.sh`: enable APIs, Firestore (us-central1), Artifact Registry, runtime and
      scheduler service accounts with least privilege, secrets from `.env` without echoing,
      Cloud Build image, two Cloud Run Jobs, two Scheduler jobs (Asia/Ho_Chi_Minh), budget alerts.
- [x] New project created and linked to the trial billing account (user-approved).
- [x] Setup, configuration and operations notes in `docs/setup-and-operations.md` (repo rule: markdown only under docs/ and plans/).

## Implementation Steps

1. Dockerfile and deploy script.
2. Create the project and run `deploy.sh`.
3. Execute ingest, then digest, from Cloud Run; check Discord output.
4. Force an error path to check `#he-thong`.

## Todo

- [x] Dockerfile + deploy.sh
- [x] Project + deploy
- [x] Live ingest and digest
- [x] Ops alert check
- [x] Operations docs

## Risks and rollback

News sites may block GCP egress IPs more than residential IPs; measured during the
live run. Rollback: `gcloud scheduler jobs pause` stops all activity; deleting the
project removes every resource.

## Success Criteria

Live digest visible in `#tin-tuc`; scheduler jobs listed with the correct time zone.
