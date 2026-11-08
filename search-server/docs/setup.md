# One-time setup

You do these steps **once**, on a new machine or after wiping the volumes. Afterwards, everything
is stored in the `.env` file and the Docker volumes, and `docker compose up -d` is enough.

**Quick checklist**

1. [Fill in the secrets you make up yourself](#1-make-up-the-secrets)
2. [Start Meilisearch and create the index + embedder](#2-create-the-index-and-the-embedder)
3. [Create the two Meilisearch keys](#3-create-the-meilisearch-keys)
4. [Download the Ollama model](#4-download-the-ollama-model)
5. [Connect MongoDB Atlas](#5-connect-mongodb-atlas)
6. [Create the Cloudflare tunnel](#6-create-the-cloudflare-tunnel)
7. [Start everything and test](#7-start-everything-and-test)

Run all commands from `search-server/`.

---

## 1. Make up the secrets

```bash
cp .env.example .env
openssl rand -hex 32   # run twice: one value for MEILI_MASTER_KEY, one for API_KEY
```

Put the two values into `.env`:

- `MEILI_MASTER_KEY` is the admin password of Meilisearch. Only you use it, for setup.
  None of the apps use it.
- `API_KEY` is the password the web app must send to search-api. The same value goes into
  `SEARCH_API_KEY` in the repo-root `.env`.

For the commands below, load `.env` into your shell:

```bash
set -a; source .env; set +a
```

## 2. Create the index and the embedder

Start only Meilisearch first:

```bash
docker compose up -d meilisearch
```

**Why an "embedder"?** Plain search matches words. We also want to match **meaning**, so that
"segregation in a cinema" finds a record that says "theatre". An embedder is a small AI model that
turns each record into a list of numbers (a *vector*). Texts with similar meaning get similar
vectors. We use a **multilingual** model because the records are in English and French.

This one request creates the `records` index **and** sets up its embedder:

```bash
curl -X PATCH http://127.0.0.1:7700/indexes/records/settings/embedders \
  -H "Authorization: Bearer $MEILI_MASTER_KEY" \
  -H "Content-Type: application/json" \
  --data '{
    "default": {
      "source": "huggingFace",
      "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
      "documentTemplate": "{{doc.title}}. {% if doc.summary %}{{doc.summary}}{% else %}{{doc.description}}{% endif %}"
    }
  }'
```

- `default` is the name. `main.py` refers to it (`"embedder": "default"`).
- `documentTemplate` decides **which text gets embedded**: the title and the `summary` (the full
  text). Records without a summary use the short `description` instead. The `attribution` field is
  still searchable by keyword, but not by meaning.
- Only the start of a long summary counts: Meilisearch cuts the template text at 400 bytes
  (`documentTemplateMaxBytes`), and the model itself only reads about 128 tokens.
- To change the template on an existing index, just run this request again. Meilisearch then
  re-computes the embeddings of all records (no re-sync needed).
- Meilisearch downloads the model the first time, which can take a minute or two. The model is
  stored in the `meili_data` volume.

The request runs in the background. Check that it finished:

```bash
curl -s http://127.0.0.1:7700/tasks?limit=1 -H "Authorization: Bearer $MEILI_MASTER_KEY"
# look for "status":"succeeded"
```

### Allow filtering by category and attribution (facets)

By default Meilisearch can't filter or count by any field. This request tells it which fields the
search page may filter by (the checkboxes, with a count next to each value):

```bash
curl -X PUT http://127.0.0.1:7700/indexes/records/settings/filterable-attributes \
  -H "Authorization: Bearer $MEILI_MASTER_KEY" \
  -H "Content-Type: application/json" \
  --data '["contentcategory", "attribution"]'
```

- Meilisearch builds an extra internal index for these fields. With many records this takes a
  moment; check `/tasks?limit=1` as above.
- To add a field later (e.g. `resourceformat`), send the **whole** list again. `PUT` replaces the
  list; it doesn't add to it.
- The search key needs no change: the `search` permission covers filters and counts.
- Records without a category are stored as `"uncategorized"` by sync, because Meilisearch can't
  filter or count empty values.

## 3. Create the Meilisearch keys

Each app gets its own key with **only the permissions it needs**. If a key leaks, the damage stays
small: the search key can't delete anything.

**Search key** (for search-api: can only search):

```bash
curl -X POST http://127.0.0.1:7700/keys \
  -H "Authorization: Bearer $MEILI_MASTER_KEY" \
  -H "Content-Type: application/json" \
  --data '{"name": "search-api", "actions": ["search"], "indexes": ["records"], "expiresAt": null}'
```

**Sync key** (for sync: can add and delete documents):

```bash
curl -X POST http://127.0.0.1:7700/keys \
  -H "Authorization: Bearer $MEILI_MASTER_KEY" \
  -H "Content-Type: application/json" \
  --data '{"name": "sync-job", "actions": ["documents.add", "documents.delete", "tasks.get"], "indexes": ["records"], "expiresAt": null}'
```

Each response contains a `"key"` field, a 64-character value. Copy it into `.env` as
`MEILI_SEARCH_KEY` and `MEILI_SYNC_KEY`. Don't use the `"uid"` field; that's the key's id, not
the key itself.

Lost a key? List them again with
`curl -s http://127.0.0.1:7700/keys -H "Authorization: Bearer $MEILI_MASTER_KEY"`.

## 4. Download the Ollama model

The Ollama container starts **empty**. It has no model until you download one:

```bash
docker compose up -d ollama
docker compose exec ollama ollama pull qwen2.5:3b
docker compose exec ollama ollama list    # should now show qwen2.5:3b
```

The model is stored in the `ollama_data` volume, so you only download it once. To use a different
model, pull it and set `OLLAMA_MODEL` for `search-api` in `docker-compose.yml`.

**Optional: Gemini.** Put a Google AI Studio key into `GEMINI_API_KEY` and set
`SUMMARY_PROVIDER=gemini` in `docker-compose.yml`. Gemini is faster. If it fails, search-api
falls back to Ollama automatically.

## 5. Connect MongoDB Atlas

Fill in `ATLAS_URI`, `ATLAS_DB` and `ATLAS_COLLECTION` in `.env`.

In Atlas → **Network Access**, allow the **public IP of the server**. Otherwise the sync can't
connect. If the server's IP changes (common on home internet), update it there.

## 6. Create the Cloudflare tunnel

**Why a tunnel?** The server doesn't need any open ports. `cloudflared` makes an **outgoing**
connection to Cloudflare. When someone calls the public hostname, Cloudflare sends the request back
through that connection. The server stays hidden, and Cloudflare handles HTTPS.

1. In the Cloudflare **Zero Trust** dashboard → *Networks* → *Tunnels*, create a tunnel of type
   *Cloudflared*.
2. Copy the **token** from the install command it shows (the long value after `--token`). Put it
   into `.env` as `TUNNEL_TOKEN`. Don't install anything; our `cloudflared` container does that job.
3. Add a **public hostname** route:
   - hostname: the domain you want, e.g. `search.example.com`
   - path: empty
   - service: `http://search-api:3000`

   `search-api` works as a hostname because `cloudflared` runs in the same Docker network, where
   each service is reachable by its name.
4. Recommended: in the Cloudflare dashboard for that domain, add a **rate-limiting rule** on the URI
   path `/api/search`. Every search can call an AI model, so this stops someone from flooding it.

## 7. Start everything and test

```bash
docker compose up -d --build
docker compose ps
docker compose logs sync          # should say "Full sync: sent N records" then "Watching for changes..."
curl https://<search-hostname>/health
```

Then run a real search. The `curl` example is in the [README](../README.md#quick-start).
