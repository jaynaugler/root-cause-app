# How records get into the search (`sync/sync.py`)

The records live in **MongoDB Atlas**. Meilisearch has its own copy, because it can only search
what it has stored. The `sync` container keeps that copy up to date.

## Quick reference

- **On start:** deletes everything in the `records` index and copies all records from Atlas
  (*full sync*).
- **Then:** listens to Atlas and applies every insert, update and delete within seconds (*watch*).
- **On any error:** waits 10 seconds and starts again from the full sync.
- **Logs:** `docker compose logs -f sync`
  - `Full sync: sent N records` means the copy finished.
  - `Watching for changes...` means it's now listening.
  - `Added or updated <id>` / `Removed <id>` means a change was applied.
- **Force a fresh copy:** `docker compose restart sync`

| Variable           | Default                   | Meaning                                                   |
| ------------------ | ------------------------- | --------------------------------------------------------- |
| `ATLAS_URI`        | (required)                | Atlas connection string                                   |
| `ATLAS_DB`         | (required)                | Database name                                              |
| `ATLAS_COLLECTION` | (required)                | Collection with the records                               |
| `MEILI_URL`        | `http://meilisearch:7700` | Where Meilisearch is                                       |
| `MEILI_SYNC_KEY`   | (required)                | Meilisearch key that can add/delete documents             |
| `MEILI_INDEX`      | `records`                 | Index name. search-api uses `records` too                 |
| `APPROVED_ONLY`    | `false` (compose: `true`) | `true` = only records with `status: "approved"` are searchable |

## How it works

### What gets copied: `to_meili()`

Not the whole Mongo document, only the fields the search needs:

```
title, description, summary, attribution, link, resourceformat, contentcategory, imgurl, createdAt
```

Two conversions are needed because Meilisearch only understands plain JSON:
- Mongo's `_id` (an `ObjectId`) becomes a string `id`.
- `createdAt` (a Python `datetime`) becomes an ISO text like `2026-11-07T10:00:00`.

And `createdAtTs`: the same date as a number (milliseconds since 1970), so browsing can sort
newest first. Text dates sort correctly only if every one has the same format, and they don't:
`2026-11-07T17:25:37.013000` vs `2026-11-07T17:25:38`. pymongo returns UTC dates without a
timezone, so sync marks them as UTC before converting.

And one for the category filter: an empty `contentcategory` (`null`) becomes `"uncategorized"`,
because Meilisearch can't filter or count empty values. The record in MongoDB stays unchanged.

Meilisearch then creates the embedding (the "meaning" vector) for each new record by itself, from
title and summary (or description when there is no summary). See [setup](setup.md#2-create-the-index-and-the-embedder).

### Step 1: full sync

```python
meili.delete(".../documents")           # empty the index
for start in range(0, len(records), 500):
    add(records[start:start + 500])     # send in batches of 500
```

**Why start from scratch?** It's the simplest way to be sure the copy matches Atlas, including
records deleted while sync wasn't running. **Why batches?** One huge request could hit size limits
or time out. 500 at a time is safe.

The index keeps its settings (embedder etc.). Only the documents are deleted.

### Step 2: watch (change stream)

```python
with collection.watch(pipeline, full_document="updateLookup") as stream:
    for change in stream:
```

A **change stream** is a MongoDB feature: instead of asking "anything new?" again and again, we
keep a connection open and Atlas **pushes** each change to us as it happens. This only works on a
replica set, which Atlas always is.

`full_document="updateLookup"` asks Atlas to include the **whole current document** with every
update, not just the changed fields, so we can send a complete record to Meilisearch.

For each change:

| What happened in Atlas                        | What sync does in Meilisearch          |
| --------------------------------------------- | -------------------------------------- |
| record deleted                                | remove it                              |
| record added or changed, and visible          | add it (same `id` = replace)           |
| record changed, but no longer visible         | remove it                              |

"Visible" (`is_visible()`) means: always, if `APPROVED_ONLY=false`. Otherwise only if
`status == "approved"`. This lets a moderator approve a record and have it show up in search
right away. Un-approving removes it again.

### Step 3: errors

The whole thing runs in a `while True` loop. If anything fails (Atlas unreachable, network drop,
Meilisearch restarting), it logs the error, waits 10 seconds and starts over **from the full sync**.
Because the full sync rebuilds everything, no change can be missed, even ones that happened
while sync was down.

## Good to know

- **Every restart re-copies everything,** and Meilisearch re-computes all embeddings. With a few
  thousand records that's fine. With many more it gets slow and CPU-heavy. Then it would be worth
  saving the change stream's *resume token* instead of starting over.
- **During a full sync, search briefly has fewer or no results,** between "empty the index" and
  "batches added".
- **sync must be able to reach Atlas:** the server's public IP must be allowed in Atlas → Network Access.
- **The search key can't write.** Only this container has write access (`MEILI_SYNC_KEY`), so
  search-api can never change the index by mistake.

## Changing the code

```bash
docker compose up -d --build sync
docker compose logs -f sync
```
