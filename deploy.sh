#!/usr/bin/env bash
# Deploy or update the news digest on Google Cloud. Safe to rerun after any change.
#
# Reads .env (see .env.example): GCP_PROJECT, GCP_REGION and the three Discord webhook URLs.
# The project must already exist with billing linked. Webhook URLs go to Secret Manager and
# are never printed.
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] || { echo "Missing .env (copy .env.example)"; exit 1; }
set -a
# shellcheck disable=SC1090
source <(tr -d '\r' < .env)  # tolerate Windows line endings
set +a
: "${GCP_PROJECT:?GCP_PROJECT is empty in .env}"
REGION="${GCP_REGION:-us-central1}"
for name in DISCORD_WEBHOOK_DIGEST DISCORD_WEBHOOK_HOT DISCORD_WEBHOOK_OPS; do
  [ -n "${!name:-}" ] || { echo "$name is empty in .env"; exit 1; }
done

gc() { gcloud --project="$GCP_PROJECT" --quiet "$@"; }
exists() { "$@" >/dev/null 2>&1; }
RUNNER="get-news-runner@$GCP_PROJECT.iam.gserviceaccount.com"
SCHEDULER="get-news-scheduler@$GCP_PROJECT.iam.gserviceaccount.com"
PROJECT_NUMBER=$(gc projects describe "$GCP_PROJECT" --format='value(projectNumber)')

echo "==> 0/8 Tests and configuration check"
# A typo in sources.yaml or settings.yaml would otherwise stop every job silently.
uv run pytest -q

echo "==> 1/8 Enabling APIs"
gc services enable run.googleapis.com cloudscheduler.googleapis.com firestore.googleapis.com \
  aiplatform.googleapis.com secretmanager.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com compute.googleapis.com billingbudgets.googleapis.com

echo "==> 2/8 Firestore"
exists gc firestore databases describe --database="(default)" \
  || gc firestore databases create --location="$REGION" --type=firestore-native
# Article lists and centroids are never queried; old clusters expire through TTL.
for field in articles centroid; do
  gc firestore indexes fields update "$field" --collection-group=clusters --disable-indexes --async >/dev/null
done
gc firestore fields ttls update expire_at --collection-group=clusters --enable-ttl --async >/dev/null

echo "==> 3/8 Service accounts"
exists gc iam service-accounts describe "$RUNNER" \
  || gc iam service-accounts create get-news-runner --display-name="get-news jobs"
exists gc iam service-accounts describe "$SCHEDULER" \
  || gc iam service-accounts create get-news-scheduler --display-name="get-news scheduler"
for role in roles/datastore.user roles/aiplatform.user roles/logging.logWriter; do
  gc projects add-iam-policy-binding "$GCP_PROJECT" --member="serviceAccount:$RUNNER" --role="$role" --condition=None >/dev/null
done
# Cloud Build runs as the Compute Engine default service account in new projects.
gc projects add-iam-policy-binding "$GCP_PROJECT" --condition=None >/dev/null \
  --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" --role=roles/cloudbuild.builds.builder

echo "==> 4/8 Secrets"
put_secret() {
  local secret=$1 value=$2
  exists gc secrets describe "$secret" || gc secrets create "$secret" --replication-policy=automatic >/dev/null
  if [ "$(gc secrets versions access latest --secret="$secret" 2>/dev/null || true)" != "$value" ]; then
    printf '%s' "$value" | gc secrets versions add "$secret" --data-file=- >/dev/null
    echo "    $secret updated"
  fi
  gc secrets add-iam-policy-binding "$secret" --member="serviceAccount:$RUNNER" \
    --role=roles/secretmanager.secretAccessor >/dev/null
}
put_secret discord-webhook-digest "$DISCORD_WEBHOOK_DIGEST"
put_secret discord-webhook-hot "$DISCORD_WEBHOOK_HOT"
put_secret discord-webhook-ops "$DISCORD_WEBHOOK_OPS"

echo "==> 5/8 Container image"
exists gc artifacts repositories describe get-news --location="$REGION" \
  || gc artifacts repositories create get-news --repository-format=docker --location="$REGION"
POLICY=.artifact-cleanup-policy.json  # relative path: works with gcloud on Windows too
cat >"$POLICY" <<'JSON'
[{"name": "keep-recent", "action": {"type": "Keep"}, "mostRecentVersions": {"keepCount": 3}},
 {"name": "delete-rest", "action": {"type": "Delete"}, "condition": {"tagState": "any"}}]
JSON
gc artifacts repositories set-cleanup-policies get-news --location="$REGION" --policy="$POLICY" --no-dry-run >/dev/null
rm -f "$POLICY"
IMAGE="$REGION-docker.pkg.dev/$GCP_PROJECT/get-news/app:$(date +%Y%m%d-%H%M%S)"
gc builds submit --region="$REGION" --tag="$IMAGE" .

echo "==> 6/8 Cloud Run jobs"
COMMON=(--image="$IMAGE" --region="$REGION" --service-account="$RUNNER" --tasks=1 --cpu=1 --memory=1Gi
  --set-env-vars="GCP_PROJECT=$GCP_PROJECT,GCP_LOCATION=global")
gc run jobs deploy get-news-ingest "${COMMON[@]}" --args=ingest --task-timeout=10m --max-retries=0 \
  --set-secrets="DISCORD_WEBHOOK_HOT=discord-webhook-hot:latest,DISCORD_WEBHOOK_OPS=discord-webhook-ops:latest"
gc run jobs deploy get-news-digest "${COMMON[@]}" --args=digest --task-timeout=20m --max-retries=1 \
  --set-secrets="DISCORD_WEBHOOK_DIGEST=discord-webhook-digest:latest,DISCORD_WEBHOOK_OPS=discord-webhook-ops:latest"

echo "==> 7/8 Schedules (Asia/Ho_Chi_Minh)"
schedule() {
  local name=$1 cron=$2 verb=create
  gc run jobs add-iam-policy-binding "$name" --region="$REGION" --member="serviceAccount:$SCHEDULER" \
    --role=roles/run.invoker >/dev/null
  exists gc scheduler jobs describe "$name" --location="$REGION" && verb=update
  gc scheduler jobs "$verb" http "$name" --location="$REGION" --schedule="$cron" --time-zone=Asia/Ho_Chi_Minh \
    --uri="https://run.googleapis.com/v2/projects/$GCP_PROJECT/locations/$REGION/jobs/$name:run" \
    --http-method=POST --oauth-service-account-email="$SCHEDULER" >/dev/null
  echo "    $name: $cron"
}
# Ingest is offset from the digest so the two never run at the same moment.
schedule get-news-ingest "5,20,35,50 * * * *"
schedule get-news-digest "0 7,19 * * *"  # keep in sync with digest.slots in settings.yaml

BUDGET="${BUDGET_AMOUNT:-20USD}"  # must use the billing account's currency, e.g. 520000VND
echo "==> 8/8 Budget alerts (50% and 100% of $BUDGET, emailed to billing admins)"
BILLING=$(gc billing projects describe "$GCP_PROJECT" --format='value(billingAccountName)' | sed 's|billingAccounts/||')
if ! gcloud billing budgets list --billing-project="$GCP_PROJECT" --billing-account="$BILLING" \
  --format='value(displayName)' | grep -qx "get-news"; then
  gcloud billing budgets create --billing-project="$GCP_PROJECT" --billing-account="$BILLING" \
    --display-name="get-news" --budget-amount="$BUDGET" \
    --threshold-rule=percent=0.5 --threshold-rule=percent=1.0 --filter-projects="projects/$GCP_PROJECT" >/dev/null
fi

echo "Deployed $IMAGE"
echo "Run now:  gcloud run jobs execute get-news-ingest --region=$REGION --project=$GCP_PROJECT"
