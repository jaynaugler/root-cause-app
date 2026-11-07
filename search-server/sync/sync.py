import logging
import os
import time
from datetime import datetime

import httpx
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sync")

# Settings (from docker-compose.yml / .env)
ATLAS_URI = os.environ["ATLAS_URI"]
ATLAS_DB = os.environ["ATLAS_DB"]
ATLAS_COLLECTION = os.environ["ATLAS_COLLECTION"]
MEILI_URL = os.environ.get("MEILI_URL", "http://meilisearch:7700")
MEILI_SYNC_KEY = os.environ["MEILI_SYNC_KEY"]
MEILI_INDEX = os.environ.get("MEILI_INDEX", "records")
APPROVED_ONLY = os.environ.get("APPROVED_ONLY", "false").lower() == "true"

# Fields copied from MongoDB to Meilisearch
# (description = short card teaser; summary = full text used for search)
FIELDS = ["title", "description", "summary", "attribution", "link",
          "resourceformat", "contentcategory", "imgurl"]

meili = httpx.Client(
    base_url=MEILI_URL,
    headers={"Authorization": f"Bearer {MEILI_SYNC_KEY}"},
    timeout=30,
)


def is_visible(doc):
    """Should this record be searchable?"""
    return (not APPROVED_ONLY) or doc.get("status") == "approved"


def to_meili(doc):
    """Convert a MongoDB record into a Meilisearch record."""
    record = {"id": str(doc["_id"])}
    for field in FIELDS:
        record[field] = doc.get(field)
    created = doc.get("createdAt")
    record["createdAt"] = created.isoformat() if isinstance(created, datetime) else created
    return record


def add(records):
    r = meili.post(f"/indexes/{MEILI_INDEX}/documents",
                   params={"primaryKey": "id"}, json=records)
    r.raise_for_status()


def remove(record_id):
    r = meili.delete(f"/indexes/{MEILI_INDEX}/documents/{record_id}")
    r.raise_for_status()


def full_sync(collection):
    """Replace everything in Meilisearch with the current MongoDB data."""
    query = {"status": "approved"} if APPROVED_ONLY else {}
    records = [to_meili(doc) for doc in collection.find(query)]
    meili.delete(f"/indexes/{MEILI_INDEX}/documents").raise_for_status()
    for start in range(0, len(records), 500):
        add(records[start:start + 500])
    log.info("Full sync: sent %d records", len(records))


def watch(collection):
    """Listen for changes in MongoDB and apply them to Meilisearch."""
    pipeline = [{"$match": {"operationType": {"$in": ["insert", "update", "replace", "delete"]}}}]
    with collection.watch(pipeline, full_document="updateLookup") as stream:
        log.info("Watching for changes...")
        for change in stream:
            record_id = str(change["documentKey"]["_id"])
            doc = change.get("fullDocument")
            if change["operationType"] == "delete" or doc is None:
                remove(record_id)
                log.info("Removed %s", record_id)
            elif is_visible(doc):
                add([to_meili(doc)])
                log.info("Added or updated %s", record_id)
            else:
                remove(record_id)
                log.info("Removed %s (not approved)", record_id)


def main():
    while True:
        try:
            client = MongoClient(ATLAS_URI)
            collection = client[ATLAS_DB][ATLAS_COLLECTION]
            full_sync(collection)
            watch(collection)
        except Exception as error:
            log.error("Sync error: %s. Retrying in 10 seconds.", error)
            time.sleep(10)


if __name__ == "__main__":
    main()