# How a search works (`search-api/main.py`)

`main.py` is one small FastAPI app with five endpoints:

- `GET /health` returns `{"status": "ok"}`. It's used to check that the service is alive.
- `GET /health/ai` checks that the AI models can really answer, see
  [AI health check](#ai-health-check-get-healthai).
- `POST /api/search` is the real work, described below.
- `POST /api/browse` lists the newest records without a question, see
  [Browsing](#browsing-post-apibrowse).
- `POST /api/facets` lists the values of one field for a filter panel, see
  [Filter panels](#filter-panels-post-apifacets).

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
| `offset`   | no       | 0 or more, default 0                     | How many records to skip, for the next page. See [Paging](#paging-offset) |
| `provider` | no       | `"ollama"` or `"gemini"`                 | Which AI writes the answer (default from settings) |
| `history`  | no       | max 3 turns, oldest first; each `question` ≤ 500, `summary` ≤ 2000 chars | Earlier questions and answers, for follow-ups |
| `summary`  | no       | `true` (default) or `false`              | `false` skips the AI: only records and counts, in milliseconds (used for filter clicks) |
| `filters`  | no       | keys only `contentcategory`, `attribution`, `resourceformat`; max 20 values each, 1–200 chars | Only records with these values (the checkboxes). See [Filters](#filters-and-counts-facets) |

**Response**

```json
{
  "summary": "Yes. In 2010 she received a posthumous free pardon … [1]",
  "provider": "gemini",
  "results": [
    { "id": "…", "title": "…", "description": "…", "summary": "…", "attribution": "…",
      "link": "…", "sitelink": "…", "resourceformat": "pdf", "contentcategory": "history", "imgurl": null,
      "createdAt": "…", "_rankingScore": 0.83 }
  ],
  "total": 14,
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
- `total` is how many records match the question and the filters, not only the `limit` shown.
  It is exact up to 1000 and stops there (see [why](#filters-and-counts-facets)).
- `facets` counts **all** matching records per value, not only the `limit` shown.

**Errors:** `401` wrong key · `422` request breaks a rule above · `502` Meilisearch failed.

## The flow, step by step

```
POST /api/search
   │
   ├─ 1. check X-API-Key ─────────────────────────── wrong → 401
   ├─ 2. build search text: last 2 earlier questions + new question
   ├─ 3. Meilisearch hybrid search (keywords + meaning, + filters, as one /multi-search) ── error → 502
   │       → hits with score ≥ 0.7 (nothing? again with ≥ 0.6), at most `limit`
   │       → counts per filter value (facets) and the total
   ├─ 4. no hits, or "summary": false? → summary = null, skip to 6
   ├─ 5. build prompt (history + top 5 hits + question)
   │       → Gemini (if chosen) ──fails──► Ollama ──fails──► summary = null
   │       → trim answer to 2000 characters
   └─ 6. return { summary, provider, results, total, facets }
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

We also send `"facets": [...]`, so Meilisearch returns how many matching records have each value
(`facetDistribution`). We return it as `facets`.

**Counting a field without its own filter** (`build_searches()`). If the user checks "people",
a normal search would count only people, and "history (7)" would disappear, so the user couldn't
add it. Shops count each group **without its own checkboxes** (they are alternatives, OR), but
**with** the other groups' checkboxes (AND). Example with "people" and "pdf" checked:

| Search | Filter | Used for |
| ------ | ------ | -------- |
| main | people AND pdf | `results` only (`limit` from the request, e.g. 8) |
| count 1 | people AND pdf | counts of fields with nothing checked (`attribution`), and `total` |
| count 2 | only pdf | counts of `contentcategory` |
| count 3 | only people | counts of `resourceformat` |

All of them go to Meilisearch in **one** request (`/multi-search`): the main search, one count
search with all filters, and one per field with checked values. Without filters that's 2
searches. The count search with all filters is **always** sent, even when every field has checked
values (then it counts no field). Its number of hits is `total` (`total()` in the code).

**Why counts never come from the main search, and why the count searches use `limit: 1000`:**
Meilisearch applies the score threshold only to records it actually *ranks*, and it stops
ranking after `limit` records. If more records pass the threshold than `limit` allows, it never
reaches the weak ones, so it can't exclude them, and they end up in the counts. Example (3 good
matches, 57 weak ones, threshold 0.7):

| `limit` | Count for "book" |
| ------- | ---------------- |
| 1, 2, 3 | 57 (wrong, includes the weak matches) |
| 4 or more | 1 (right) |

So the count searches rank up to `COUNT_LIMIT` = 1000 records (Meilisearch's maximum) and return
only each record's `id`. Counts are exact as long as fewer than 1000 records pass the threshold.
Not `limit: 0`: that makes Meilisearch skip the meaning half of a hybrid search, so records that
only match by meaning would be missing.

All searches use the **same** threshold. If the main search finds nothing at 0.7, the whole set is
re-run at 0.6 (`run_with_fallback()`). Meilisearch applies the threshold to hits and counts alike, so the counts always
describe the results the user sees.

Meilisearch leaves out values with 0 matches. A checked value can therefore be missing from
`facets`; the UI must still show it (as 0) so the user can uncheck it.

### Paging: `offset`

The web app shows the first `limit` records, and a "show more" button asks again with
`offset` = the number already shown. Only the **main** search uses `offset`. The count searches
always start at 0, so `total` and `facets` stay the same on every page.

Meilisearch never returns records past the 1000th (`maxTotalHits`), so pages after that come
back empty. `total` also stops at 1000, so the web app never asks for them.

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

We return the summary, which provider actually answered, the raw Meilisearch hits, the total
and the counts. The web
app shows the answer on top and the records below it.

## Browsing: `POST /api/browse`

The search page shows the archive **before** any question: the newest records, with filter pills
and counts for the whole archive. Clicking a pill filters the list right away.

```http
POST /api/browse
X-API-Key: <API_KEY>
Content-Type: application/json

{ "limit": 12, "filters": { "contentcategory": ["people"] } }
```

| Field     | Required | Rules                    | Meaning                         |
| --------- | -------- | ------------------------ | ------------------------------- |
| `limit`   | no       | 1–50, default 12         | How many records to return      |
| `offset`  | no       | 0 or more, default 0     | How many records to skip, for the next page |
| `filters` | no       | same as in `/api/search` | Only records with these values  |

The response has `results`, `total` and `facets`, in the same shape as `/api/search`, but no
`summary`.

How it differs from a search:

- **No question:** Meilisearch's *placeholder search* (`"q": ""`) returns every record that passes
  the filters. So there's no AI, no embedding and no score threshold, and the counts are simply
  exact.
- **Sorted newest first** by `createdAtTs` (a number written by sync). The field must be sortable
  in Meilisearch, see [setup](setup.md#allow-sorting-by-date-browsing).
- **Counting** is the same as for a search (`build_searches()`): each field without its own
  filter, so checking "people" keeps "history (7)" visible.
- Only approved records are in Meilisearch at all (`APPROVED_ONLY=true` in sync).

## Filter panels: `POST /api/facets`

Each filter pill on the search page opens a panel with the values of one field, a checkbox and a
count each. Long lists (hundreds of sources) are never sent whole: the panel asks for one page at
a time, and the text typed in its search field is matched here, on the server.

```http
POST /api/facets
X-API-Key: <API_KEY>
Content-Type: application/json

{
  "question": "Who was Viola Desmond?",
  "history": [],
  "filters": { "contentcategory": ["people"], "attribution": ["Black Cultural Centre for Nova Scotia"] },
  "facet": "attribution",
  "search": "univ",
  "sort": "count",
  "limit": 8
}
```

| Field      | Required | Rules                                  | Meaning                                          |
| ---------- | -------- | -------------------------------------- | ------------------------------------------------ |
| `question`, `history`, `filters` | no | same as in `/api/search`, but `question` may be empty | The search the records on the page come from. No question = browsing, see below |
| `facet`    | yes      | one of the `FacetField` names          | The field whose values the panel lists           |
| `search`   | no       | 0–100 characters                       | Only values containing this text. Case and accents don't matter: `univ` finds "Université" |
| `sort`     | no       | `"count"` (default) or `"alpha"`       | Most records first (ties A–Z), or A–Z            |
| `limit`    | no       | 1–100, default 8                       | Values per page (the web app: 8 first, 50 for A–Z) |
| `cursor`   | no       | the `next_cursor` of the previous page | Which page. Leave it out for the first one      |

**Response**

```json
{
  "options": [
    { "value": "Dalhousie University Libraries", "count": 11 },
    { "value": "Université Sainte-Anne", "count": 3 }
  ],
  "selected": [{ "value": "Black Cultural Centre for Nova Scotia", "count": 41 }],
  "total_options": 2,
  "next_cursor": null
}
```

- `options` is one page of values that match `search`. Checked values are included too, in their
  normal place. Labels ("People", "PDF") are added by the web app.
- `selected` is the field's checked values, **whatever** `search` says. The panel pins them on top,
  so it needs no extra request for them.
- `total_options` counts the matching values on all pages. `next_cursor` is `null` on the last
  page. A cursor is just base64 JSON (`{"o": 8}` = start at the 9th value), but the web app only
  sends back what it got, so the format can change later. A broken cursor answers `422`.

**The counts are the same as in `/api/search`.** The field is counted without its own filter, with
the other filters (see [Filters and counts](#filters-and-counts-facets)). The threshold is chosen
the same way too (`run_with_fallback()`): a main search with `limit: 1` decides whether 0.7 or 0.6
applies. Without this, the panel could say "People (12)" while the page shows records from the
looser threshold.

**Browsing (no question).** Before the first question, the search page lets people filter the
newest records ([`/api/browse`](#browsing-post-apibrowse)). Its panels send no `question` (or an
empty one). Then every search here is a placeholder search (`"q": ""`) with no threshold, like
`/api/browse`, and the counts are those of the whole archive (with the other filters). `history`
is ignored.

**Values with 0 matches.** Meilisearch leaves them out of the counts. To still list them
(the panel shows them disabled, last), a second request asks for every value in the whole archive:
a placeholder search (`"q": ""`) with no filter and no threshold. It can't share the
`/multi-search` with the others, because those all get the threshold. The two requests run at the
same time (`asyncio.gather`). Checked values are always listed, even ones that no longer exist in
the archive, so they can be unchecked.

**Order.** `count`: most records first, ties A–Z. `alpha`: A–Z. In both, values with 0 records go
last, except checked ones (`sort_options()`).

**Long lists:** Meilisearch returns at most `maxValuesPerFacet` values per field (100 by default).
Raise it before the source list grows past that, see
[setup](setup.md#allow-long-value-lists-filter-panels).

## AI health check: `GET /health/ai`

`/health` only says that search-api is running. `/health/ai` checks that the AI models can
really **write** an answer: it asks each one to reply "OK".

```http
GET /health/ai
X-API-Key: <API_KEY>
```

```json
{
  "status": "healthy",
  "checked_at": 1794234000.5,
  "providers": { "ollama": "healthy", "gemini": "healthy" }
}
```

- Each provider is `healthy`, `unhealthy` or `not_configured` (Gemini without `GEMINI_API_KEY`).
- `status` is `healthy` when no provider is `unhealthy`. Otherwise the answer is `503`.
- `checked_at` is when the check really ran (Unix time in seconds).
- **Cached for 5 minutes.** Every check calls the AI, and Gemini costs money, so a page that is
  refreshed often doesn't trigger a new check each time. Each check gives up after 20 seconds.
- It needs the API key, like the search endpoints. Without it: `401`.

The web app shows it on its `/health` page, through `web/src/routes/health/search-ai/+server.ts`.

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
| `SUMMARY_PROVIDER` | `ollama`                   | yes (`gemini`)  | Default AI: `ollama` or `gemini`                 |
| `SUMMARY_SOURCES`  | `5`                        | no              | How many top hits go into the prompt             |
| `OLLAMA_URL`       | `http://ollama:11434`      | no              | Where Ollama is                                  |
| `OLLAMA_MODEL`     | `qwen2.5:3b`               | no              | Must be pulled first (see setup)                 |
| `OLLAMA_TIMEOUT`   | `60` seconds               | no              | Give up on Ollama after this long                |
| `GEMINI_API_KEY`   | empty                      | from `.env`     | Empty = Gemini disabled (always falls back to Ollama) |
| `GEMINI_MODEL`     | `gemini-3.5-flash-lite`    | yes             | Which Gemini model                               |
| `GEMINI_TIMEOUT`   | `20` seconds               | no              | Give up on Gemini after this long                |

`MAX_SUMMARY_CHARS` (2000) is a constant in the code, not a setting, because the web app has the
same number. See the [README](../README.md#connecting-the-web-app).

> The web app waits up to 90 seconds for an answer. If you raise `OLLAMA_TIMEOUT` a lot, raise
> that too (`AbortSignal.timeout` in `web/src/routes/+page.server.ts`).

## Changing the code

Edit `search-api/main.py`, then rebuild and check the logs:

```bash
docker compose up -d --build search-api
docker compose logs -f search-api
```

The container copies `main.py` in at **build** time. Without `--build`, your change isn't used.
