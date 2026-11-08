# How a search works (`search-api/main.py`)

`main.py` is one small FastAPI app (about 200 lines) with two endpoints:

- `GET /health` returns `{"status": "ok"}`. It's used to check that the service is alive.
- `POST /api/search` is the real work, described below.

## Quick reference

**Request**

```http
POST /api/search
X-API-Key: <API_KEY>
Content-Type: application/json

{
  "question": "Was she pardoned?",
  "limit": 8,
  "provider": "gemini",
  "history": [
    { "question": "Who was Viola Desmond?", "summary": "Viola Desmond was a businesswoman who … [1]" }
  ],
  "filters": { "contentcategory": ["people", "events"] }
}
```

| Field      | Required | Rules                                    | Meaning                                         |
| ---------- | -------- | ---------------------------------------- | ----------------------------------------------- |
| `question` | yes      | 1–500 characters                         | The new question                                |
| `limit`    | no       | 1–20, default 8                          | How many records to return at most              |
| `provider` | no       | `"ollama"` or `"gemini"`                 | Which AI writes the answer (default from settings) |
| `history`  | no       | max 3 turns, oldest first; each `question` ≤ 500, `summary` ≤ 2000 chars | Earlier questions and answers, for follow-ups |
| `filters`  | no       | keys only `contentcategory`, `attribution`, `resourceformat`; max 20 values each, 1–200 chars | Only records with these values (the checkboxes). See [Filters](#filters-and-counts-facets) |

**Response**

```json
{
  "summary": "Yes. In 2010 she received a posthumous free pardon … [1]",
  "provider": "gemini",
  "results": [
    { "id": "…", "title": "…", "description": "…", "attribution": "…", "link": "…",
      "resourceformat": "pdf", "contentcategory": "history", "imgurl": null,
      "createdAt": "…", "_rankingScore": 0.83 }
  ],
  "facets": {
    "contentcategory": { "people": 12, "history": 7, "uncategorized": 24 },
    "attribution": { "Black Cultural Centre for Nova Scotia": 43 },
    "resourceformat": { "pdf": 43 }
  }
}
```

- `summary` is `null` when nothing was found, or when both AI providers failed. The `results` are
  still returned in that case.
- `provider` is the AI that **actually** answered. It can differ from the one asked for (see fallback).
- `facets` counts **all** matching records per value, not only the `limit` shown.

**Errors:** `401` wrong key · `422` request breaks a rule above · `502` Meilisearch failed.

## The flow, step by step

```
POST /api/search
   │
   ├─ 1. check X-API-Key ─────────────────────────── wrong → 401
   ├─ 2. build search text: last 2 earlier questions + new question
   ├─ 3. Meilisearch hybrid search (keywords + meaning, + filters) ── error → 502
   │       → hits with score ≥ 0.7 (nothing? again with ≥ 0.6), at most `limit`
   │       → counts per filter value (facets)
   ├─ 4. no hits? → summary = null, skip to 6
   ├─ 5. build prompt (history + top 5 hits + question)
   │       → Gemini (if chosen) ──fails──► Ollama ──fails──► summary = null
   │       → trim answer to 2000 characters
   └─ 6. return { summary, provider, results, facets }
```

### 0. Validation, before our code even runs

The two classes `Turn` and `SearchRequest` describe what a valid request looks like. FastAPI
(through *pydantic*) checks every request against them **automatically**. If something breaks a
rule, for example a 600-character question, FastAPI answers `422` and our function never runs.
This is why the function itself has no `if len(question) > 500` checks.

### 1. Check the API key

```python
if not secrets.compare_digest(x_api_key, API_KEY):
```

The web app sends the key in the `X-API-Key` header. We compare it with `secrets.compare_digest`
instead of `==`, because `==` stops at the first different character. An attacker could measure
how long the comparison takes and guess the key one character at a time. `compare_digest` always
takes the same time.

### 2. Build the search text: `search_text()`

Follow-up questions are often unclear on their own. "Was she pardoned?" doesn't say *who*. So we
search for the **last two earlier questions plus the new one**, joined together:

```
"Who was Viola Desmond? Was she pardoned?"
```

Now the search engine can find the Viola Desmond records again. We use only the questions, not the
answers: answers are long and would blur the search.

### 3. Search Meilisearch

We send one request to Meilisearch's `records` index:

| Setting                         | Value             | Why                                                                 |
| ------------------------------- | ----------------- | ------------------------------------------------------------------- |
| `hybrid.embedder`               | `"default"`       | The embedder created during [setup](setup.md#2-create-the-index-and-the-embedder) |
| `hybrid.semanticRatio`          | `0.5`             | 0 = keywords only, 1 = meaning only. 0.5 mixes both equally         |
| `rankingScoreThreshold`         | `0.7`, then `0.6` | Drop weak matches (score is 0–1), so the AI isn't fed unrelated records. See below |
| `showRankingScore`              | `true`            | Each hit includes `_rankingScore`; useful for debugging and in the UI |
| `limit`                         | from the request  | At most this many hits                                             |

**Why hybrid?** Keyword search is good at exact things: names, places, "1916". Meaning search
("semantic") is good when the words differ: "cinema" vs "theatre", or English vs French. Hybrid
combines both.

**Why 0.7, with a second try at 0.6?** All records are about the same topic, so the meaning
search gives almost *every* record about 0.6–0.68 for any question. At 0.6, "Who is Viola Desmond"
returned 20 records. At 0.7 it returns only Viola (0.85). But questions that only match by meaning
score lower: "ségrégation au cinéma" finds Viola at exactly 0.70. So when 0.7 finds **nothing**,
we search once more with `FALLBACK_THRESHOLD` (0.6): better a few loose matches than "nothing
found". Measured on 61 records (Nov 2026); re-check when the collection grows.

`semanticRatio` turned out **not** to help here: 0.5, 0.3 and 0.2 gave the same scores. It changes
how keyword and meaning results are mixed, not the score the threshold is compared with.

The threshold stays **inside Meilisearch** on purpose: Meilisearch applies it to the facet counts
too. Filtering hits in Python afterwards would make the counts disagree with the results.

### Filters and counts (facets)

`filters` from the request becomes Meilisearch's filter text in `build_filter()`:

```
{"contentcategory": ["people", "events"], "attribution": ["BCCNS"]}
→ contentcategory IN ["people", "events"] AND attribution IN ["BCCNS"]
```

**OR** between the values of one field, **AND** between fields, the way shop filters work.

**Safety:** the caller never sends filter text. pydantic accepts only the field names in
`FacetField`, and `quote()` escapes `\` and `"` in every value. So a value like
`People" OR 1=1` stays one harmless value instead of changing the filter (same idea as SQL
injection).

Every search also sends `"facets": [...]`, so Meilisearch returns how many matching records have
each value (`facetDistribution`). We return it as `facets`. Hits and counts come from the **same**
search (also when the 0.6 fallback runs), and Meilisearch applies the threshold to both, so they
always agree.

**Known limit:** when a box is checked, the other values of *that* field drop out of the counts
(check "people" and "history" shows no number). Fixing this needs a second count per field.

We use `MEILI_SEARCH_KEY`, a key that can **only search**. Even if search-api had a bug, it
couldn't change the index.

### 4–5. Write the answer: `summarize()`

If there are no hits, there's nothing to summarise, so `summary` is `null`.

Otherwise, `build_prompt()` puts together one text for the AI:

```
Previous conversation:          ← only if history was sent

Q: Who was Viola Desmond?
A: Viola Desmond was a businesswoman … [1]

Sources:

[1] Viola Desmond
Documents about the businesswoman who …
Held by: Nova Scotia Archives

[2] …                           ← at most SUMMARY_SOURCES (5) hits

Question: Was she pardoned?
```

Together with it we send `SYSTEM_PROMPT`, the fixed rules for the AI: answer **only** from the
numbered sources, cite them as `[1]`, write 2–4 sentences, answer in the question's language, and
never invent facts. The history is there only so the AI understands what "she" means. The
facts must come from the sources.

We send only the **top 5** hits, not all of them. A shorter prompt is faster (especially on
Ollama), and the weakest hits rarely help.

**Choosing the AI, with fallback:**

- `provider` from the request wins. Otherwise we use `SUMMARY_PROVIDER` from settings.
- **Gemini** (Google, external) is fast, but needs `GEMINI_API_KEY` and internet access.
- **Ollama** runs `qwen2.5:3b` on our own server. It's free and private, but slower.
- If Gemini fails (no key, timeout, error), we log a warning and **try Ollama instead**. If Ollama
  fails too, `summary` is `null`, but the user still gets the `results`. A broken AI never breaks the search.

**Trimming:** `trim()` cuts an answer down to `MAX_SUMMARY_CHARS` (2000), at the last sentence end
if possible. Why? The web app sends our answers back to us as `history`, and `Turn.summary` only
accepts 2000 characters. Without trimming, one long answer would make the **next** follow-up fail
with `422`: the API would reject its own output. Both checks use the same constant, so they
always agree. Normal answers are a few hundred characters, so this is just a safety net.

### 6. Return

We return the summary, which provider actually answered, and the raw Meilisearch hits. The web
app shows the answer on top and the records below it.

## Settings

Read from environment variables when the container starts. To change one, set it under
`search-api: environment:` in `docker-compose.yml`, then run `docker compose up -d search-api`.

| Variable           | Default                    | Set in compose? | Meaning                                         |
| ------------------ | -------------------------- | --------------- | ----------------------------------------------- |
| `API_KEY`          | (required)                 | from `.env`     | Key the caller must send as `X-API-Key`         |
| `MEILI_URL`        | `http://meilisearch:7700`  | yes             | Where Meilisearch is                             |
| `MEILI_SEARCH_KEY` | (required)                 | from `.env`     | Search-only Meilisearch key                      |
| `SEMANTIC_RATIO`   | `0.5`                      | no              | Keyword vs meaning mix (0–1)                     |
| `SCORE_THRESHOLD`  | `0.7`                      | yes (`0.7`)     | Minimum match score (0–1)                        |
| `FALLBACK_THRESHOLD` | `0.6`                    | yes (`0.6`)     | Second try when nothing reaches `SCORE_THRESHOLD`. Same value = off |
| `SUMMARY_PROVIDER` | `ollama`                   | yes (`ollama`)  | Default AI: `ollama` or `gemini`                 |
| `SUMMARY_SOURCES`  | `5`                        | no              | How many top hits go into the prompt             |
| `OLLAMA_URL`       | `http://ollama:11434`      | no              | Where Ollama is                                  |
| `OLLAMA_MODEL`     | `qwen2.5:3b`               | no              | Must be pulled first (see setup)                 |
| `OLLAMA_TIMEOUT`   | `60` seconds               | no              | Give up on Ollama after this long                |
| `GEMINI_API_KEY`   | empty                      | from `.env`     | Empty = Gemini disabled (always falls back)      |
| `GEMINI_MODEL`     | `gemini-3.5-flash-lite`    | yes             | Which Gemini model                               |
| `GEMINI_TIMEOUT`   | `20` seconds               | no              | Give up on Gemini after this long                |

`MAX_SUMMARY_CHARS` (2000) is a constant in the code, not a setting, because the web app has the
same number. See the [README](../README.md#connecting-the-web-app).

> The web app waits up to 90 seconds for an answer. If you raise `OLLAMA_TIMEOUT` a lot, raise
> that too (`AbortSignal.timeout` in `web/src/routes/search/+page.server.ts`).

## Changing the code

Edit `search-api/main.py`, then rebuild and check the logs:

```bash
docker compose up -d --build search-api
docker compose logs -f search-api
```

The container copies `main.py` in at **build** time. Without `--build`, your change isn't used.
