# search-server

The search backend for the archive hub. You ask a question in plain language
("Who challenged segregation in a theatre?") and get back:

- the **matching records**, found by meaning and not only by exact words, and
- a **short answer** written by an AI model, with citations like `[1]`, based only on those records.

Everything runs in Docker containers on one Linux machine. The web app (`web/`) reaches the
search over the internet through a Cloudflare tunnel, so the server needs no open ports.

> **More detail:**
> [docs/setup.md](docs/setup.md): one-time setup (keys, search index, AI model, tunnel) ·
> [docs/search-api.md](docs/search-api.md): how a search works (`main.py`) ·
> [docs/sync.md](docs/sync.md): how records get from MongoDB into the search index

---

## How the parts fit together

```
                      internet                    │  server (Docker, one network)
                                                  │
  Browser ──► web app (SvelteKit, /search) ──HTTPS──► cloudflared ──► search-api :3000
              keeps SEARCH_API_KEY secret         │   (tunnel)          │        │
                                                  │                     ▼        ▼
                                                  │             meilisearch    ollama  (or Gemini,
                                                  │             :7700          :11434   outside)
                                                  │                 ▲
  MongoDB Atlas ──────── change stream ───────────────► sync ──────┘
  (the real records)                              │
```

- **MongoDB Atlas** is the source of truth for the records.
- **sync** copies them into **Meilisearch** and keeps them up to date.
- **search-api** receives a question, asks Meilisearch for matching records, then asks an AI model
  (**Ollama** on this server, or **Gemini** from Google) to summarise them.
- **cloudflared** opens an outgoing tunnel to Cloudflare. Cloudflare forwards the public hostname to
  `search-api:3000`, so nothing on the server is exposed directly.

## The five containers

| Service       | What it does                                         | Where it comes from              | Reachable from          |
| ------------- | ---------------------------------------------------- | -------------------------------- | ----------------------- |
| `search-api`  | The HTTP API: search + summary (`POST /api/search`)  | **our code**: `search-api/`      | Docker network / tunnel |
| `sync`        | Copies records from Atlas into Meilisearch           | **our code**: `sync/`            | (makes calls only)      |
| `meilisearch` | Search engine; stores the index and the embeddings   | image `getmeili/meilisearch`     | `127.0.0.1:7700` on host |
| `ollama`      | Runs the local AI model (`qwen2.5:3b`)               | image `ollama/ollama`            | `127.0.0.1:11434` on host |
| `cloudflared` | Tunnel from Cloudflare to `search-api`               | image `cloudflare/cloudflared`   | (makes calls only)      |

Data that must survive restarts lives in two Docker **volumes**:
- `meili_data`: the index, the embeddings and the downloaded embedding model.
- `ollama_data`: the downloaded AI model.

Rebuilding or recreating containers does **not** delete them. `docker compose down -v` **does**.

> The first line of `docker-compose.yml` is `name: search-hub`. This fixes the Compose project
> name, and the volume names are built from it. **Don't change it**, or Compose will create new
> empty volumes and the index and model will look "gone".

---

## Quick start

Doing this for the first time on a new machine? Follow [docs/setup.md](docs/setup.md) instead.
It also covers the one-time steps. This section is the short version.

**You need:** Docker with the Compose plugin, the repo checked out, and about 5 GB free disk space
for the models.

```bash
cd search-server
cp .env.example .env      # then fill in the values (see the table below)
docker compose up -d --build
docker compose ps         # all five should be "running"
```

Check that it works through the tunnel (replace the hostname and key with your own):

```bash
curl https://<search-hostname>/health
# {"status":"ok"}

curl -X POST https://<search-hostname>/api/search \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <API_KEY from .env>" \
  -d '{"question": "Viola Desmond"}'
```

`search-api` does not publish port 3000 on the host. To check it **without** the tunnel, ask from
inside the container:

```bash
docker compose exec search-api python -c "import httpx; print(httpx.get('http://localhost:3000/health').text)"
```

## Environment variables (`search-server/.env`)

> ⚠️ **There are two `.env` files in this repo.**
> `search-server/.env` (this one) is read by Docker Compose for the containers.
> The `.env` at the **repo root** is for the web app and `api/`. Both are git-ignored; never commit them.

| Variable           | Used by       | What it is / where it comes from                                                   |
| ------------------ | ------------- | ---------------------------------------------------------------------------------- |
| `TUNNEL_TOKEN`     | cloudflared   | Token of the Cloudflare tunnel (Cloudflare Zero Trust dashboard)                   |
| `MEILI_MASTER_KEY` | meilisearch   | The "root password" of Meilisearch. You make it up: `openssl rand -hex 32`        |
| `MEILI_SEARCH_KEY` | search-api    | Meilisearch key that can **only search** `records`. Created with the master key   |
| `MEILI_SYNC_KEY`   | sync          | Meilisearch key that can **add/delete documents** in `records`. Created with the master key |
| `API_KEY`          | search-api    | Shared secret the web app must send as `X-API-Key`. You make it up: `openssl rand -hex 32` |
| `GEMINI_API_KEY`   | search-api    | Google AI Studio key. Optional; without it, summaries use Ollama only             |
| `ATLAS_URI`        | sync          | MongoDB Atlas connection string                                                    |
| `ATLAS_DB`         | sync          | Database name in Atlas                                                             |
| `ATLAS_COLLECTION` | sync          | Collection that holds the records                                                  |

How to create the two Meilisearch keys: [docs/setup.md](docs/setup.md#3-create-the-meilisearch-keys).

Some settings are written directly in `docker-compose.yml` instead of `.env`: `SUMMARY_PROVIDER`
(`ollama` or `gemini`), `GEMINI_MODEL` and `APPROVED_ONLY`. Tuning values like the score threshold
have defaults in `main.py`. See [docs/search-api.md](docs/search-api.md#settings).

## Everyday commands

Run these from `search-server/`.

| I want to…                              | Command                                          |
| --------------------------------------- | ------------------------------------------------ |
| see what is running                     | `docker compose ps`                              |
| read logs of one service                | `docker compose logs -f search-api` (or `sync`, …) |
| apply a change to `main.py` / `sync.py` | `docker compose up -d --build search-api` (or `sync`) |
| apply a change to `.env`                | `docker compose up -d` (recreates changed services) |
| restart one service                     | `docker compose restart sync`                    |
| stop everything (data is kept)          | `docker compose down`                            |

> `restart` does **not** pick up `.env` or code changes. Use `up -d` (and `--build` for code).

## Connecting the web app

The web app calls search-api only from its **server side**, so the key never reaches the browser:

- `web/src/routes/+page.server.ts`: the search action (`/api/search`) of the search page, which is
  the home page `/`
- `web/src/routes/facets/[facet]/+server.ts`: the filter panels (`/api/facets`). Not under `/api`,
  because that path belongs to the Python `api/` service.

Both check the input with the rules in `web/src/lib/server/search-params.ts` first. Set these in the **repo-root** `.env` (and in Vercel for production):

```
SEARCH_API_URL="https://<search-hostname>"   # without /api/search
SEARCH_API_KEY="<same value as API_KEY in search-server/.env>"
```

**Limits that must match on both sides.** If you change one, change the other:

| Limit                          | search-api (`main.py`)                  | web (`web/src/lib/search.ts`, `web/src/lib/server/search-params.ts`) |
| ------------------------------ | --------------------------------------- | ------------------------------------------------ |
| question length                | `max_length=500`                        | `MAX_QUESTION_CHARS = 500`                        |
| earlier turns sent as history  | `history: max_length=3`                 | `MAX_HISTORY = 3`                                 |
| answer length                  | `MAX_SUMMARY_CHARS = 2000`              | `MAX_SUMMARY_CHARS = 2000`                        |
| filter fields                  | `FacetField`                            | `FACET_FIELDS`                                    |
| checked values per field       | `Filters`: max 20, each 1–200 chars     | `filterValuesSchema`: `.max(20)`, `.min(1).max(200)` |
| panel search text / page size  | `FacetsRequest`: `search` ≤ 100, `limit` 1–100 | `facetsRequestSchema`: same                |

## Troubleshooting

| Symptom                                   | Usually means                                                                                     |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `401 Invalid API key`                     | `X-API-Key` doesn't match `API_KEY`. Check `SEARCH_API_KEY` in the root `.env`                   |
| `422` from search-api                     | The request body broke a limit (question too long, more than 3 history turns, …)                  |
| `502 Search engine error`                 | search-api couldn't search Meilisearch: wrong `MEILI_SEARCH_KEY`, or Meilisearch is down          |
| results but `summary: null`               | Both AI providers failed. `docker compose logs search-api` shows why (often an Ollama timeout or a missing model) |
| no results for anything                   | The index is empty. Check `docker compose logs sync`                                             |
| tunnel URL gives a Cloudflare error page  | `cloudflared` is down or `TUNNEL_TOKEN` is wrong. Check `docker compose logs cloudflared`        |
| Cloudflare `502 Bad gateway`, "Host: Error" | The tunnel works, but search-api isn't answering: it crashed or keeps restarting. `docker compose ps`, then `docker compose logs --tail 50 search-api`. A `ModuleNotFoundError` right after a deploy usually means the wrong file was copied to `search-api/main.py` (compare `sha256sum` with your local copy) |
| Meilisearch won't start after an update   | The images use `:latest`, and a new Meilisearch version may not read old data. Pin the previous version in `docker-compose.yml`, or re-create the index |
| sync logs `ServerSelectionTimeoutError`   | Atlas refuses the connection. Add the server's public IP to Atlas → Network Access               |
