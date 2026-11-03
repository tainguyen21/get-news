"""Firestore persistence.

Collections:
  clusters/{id}        event clusters; ingest writes content fields, delivery steps write
                       scoring and sent fields, always as merges on disjoint fields
  digests/{date}-{am|pm}  one document per digest slot, for idempotent reruns
  state/seen           compressed map article key -> [first seen epoch, cluster id]
  state/source-health  per-source run counters
  state/hot-{date}     hot alerts sent on a Vietnam calendar day
  state/heartbeat      last successful run per job
"""

from __future__ import annotations

import json
import zlib
from datetime import datetime, timedelta

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from get_news.models import Cluster

_BATCH = 400


class Store:
    def __init__(self, db: firestore.Client):
        self.db = db
        self.clusters = db.collection("clusters")
        self.digests = db.collection("digests")
        self.state = db.collection("state")

    def _query_clusters(self, field: str, op: str, value) -> list[Cluster]:
        query = self.clusters.where(filter=FieldFilter(field, op, value))
        return [Cluster.from_doc(snap.id, snap.to_dict()) for snap in query.stream()]

    def _commit(self, writes: list[tuple[firestore.DocumentReference, dict]]) -> None:
        for start in range(0, len(writes), _BATCH):
            batch = self.db.batch()
            for ref, data in writes[start : start + _BATCH]:
                batch.set(ref, data, merge=True)
            batch.commit()

    # Seen articles
    def load_seen(self) -> dict[str, list]:
        snap = self.state.document("seen").get()
        if not snap.exists:
            return {}
        return json.loads(zlib.decompress(snap.get("data")))

    def save_seen(self, seen: dict[str, list]) -> None:
        payload = zlib.compress(json.dumps(seen, separators=(",", ":")).encode())
        self.state.document("seen").set({"data": payload, "entries": len(seen)})

    # Clusters
    def clusters_updated_since(self, since: datetime) -> list[Cluster]:
        return self._query_clusters("updated_at", ">=", since)

    def clusters_hot_pending(self) -> list[Cluster]:
        return self._query_clusters("hot_pending", "==", True)

    def clusters_sent_since(self, since: datetime) -> list[Cluster]:
        found = {c.id: c for c in self._query_clusters("digest_sent_at", ">=", since)}
        found.update({c.id: c for c in self._query_clusters("hot_sent_at", ">=", since)})
        return list(found.values())

    def save_clusters(self, clusters: list[Cluster], retention: timedelta) -> None:
        self._commit([(self.clusters.document(c.id), c.content_doc(retention)) for c in clusters])

    def save_scores(self, clusters: list[Cluster]) -> None:
        self._commit(
            [
                (
                    self.clusters.document(c.id),
                    {"importance": c.importance, "category": c.category, "scored_publishers": c.scored_publishers},
                )
                for c in clusters
            ]
        )

    def set_hot_pending(self, cluster_id: str) -> None:
        self.clusters.document(cluster_id).set({"hot_pending": True}, merge=True)

    def clear_hot_pending(self, cluster_ids: list[str]) -> None:
        self._commit([(self.clusters.document(i), {"hot_pending": False}) for i in cluster_ids])

    # Hot alerts
    def hot_count(self, day: str) -> int:
        snap = self.state.document(f"hot-{day}").get()
        return snap.get("count") if snap.exists else 0

    def mark_hot_sent(self, day: str, cluster_id: str, now: datetime) -> None:
        self._commit(
            [
                (self.clusters.document(cluster_id), {"hot_sent_at": now, "hot_pending": False}),
                (
                    self.state.document(f"hot-{day}"),
                    {"count": firestore.Increment(1), "cluster_ids": firestore.ArrayUnion([cluster_id])},
                ),
            ]
        )

    # Digests
    def get_digest(self, digest_id: str) -> dict:
        snap = self.digests.document(digest_id).get()
        return snap.to_dict() if snap.exists else {}

    def update_digest(self, digest_id: str, **fields) -> None:
        self.digests.document(digest_id).set(fields, merge=True)

    def mark_digest_sent(self, digest_id: str, cluster: Cluster, now: datetime) -> None:
        self._commit(
            [
                (self.clusters.document(cluster.id), {"digest_sent_at": now, "hot_pending": False}),
                (
                    self.digests.document(digest_id),
                    {
                        "sent": firestore.ArrayUnion([cluster.id]),
                        "sent_categories": {cluster.category: firestore.Increment(1)},
                    },
                ),
            ]
        )

    # Heartbeats
    def beat(self, job: str, now: datetime) -> None:
        self.state.document("heartbeat").set({job: now}, merge=True)

    def last_beat(self, job: str) -> datetime | None:
        snap = self.state.document("heartbeat").get()
        return (snap.to_dict() or {}).get(job) if snap.exists else None

    # Source health
    def load_health(self) -> dict[str, dict]:
        snap = self.state.document("source-health").get()
        return snap.to_dict().get("sources", {}) if snap.exists else {}

    def save_health(self, health: dict[str, dict]) -> None:
        self.state.document("source-health").set({"sources": health})
