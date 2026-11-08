import asyncio
import base64
import binascii
import json
import logging
import os
import re
import secrets
import unicodedata
from typing import Annotated, Literal, get_args

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn.error")

# Meilisearch settings
MEILI_URL = os.environ.get("MEILI_URL", "http://meilisearch:7700")
MEILI_SEARCH_KEY = os.environ["MEILI_SEARCH_KEY"]
API_KEY = os.environ["API_KEY"]
SEMANTIC_RATIO = float(os.environ.get("SEMANTIC_RATIO", "0.5"))
SCORE_THRESHOLD = float(os.environ.get("SCORE_THRESHOLD", "0.7"))
# Used only when SCORE_THRESHOLD finds nothing (e.g. questions in other words or in French,
# which score lower). Set it equal to SCORE_THRESHOLD to turn the second try off.
FALLBACK_THRESHOLD = float(os.environ.get("FALLBACK_THRESHOLD", "0.6"))
# Fields the search page can filter by (the checkboxes). Must match the
# filterableAttributes set in Meilisearch, see docs/setup.md.
FacetField = Literal["contentcategory", "attribution", "resourceformat"]
FACET_FIELDS = list(get_args(FacetField))
# How many records a count search ranks. Meilisearch applies the score threshold only to records
# it ranks, and it stops ranking after `limit`. Counts are therefore only exact when `limit` is
# larger than the number of good matches. 1000 = Meilisearch's maximum (maxTotalHits).
COUNT_LIMIT = 1000

# Summary settings
SUMMARY_PROVIDER = os.environ.get("SUMMARY_PROVIDER", "ollama")
SUMMARY_SOURCES = int(os.environ.get("SUMMARY_SOURCES", "5"))
# Max answer length. Used both to trim answers we return and to validate the
# history sent back, so our own answers always pass. Mirrored in web/src/lib/search.ts.
MAX_SUMMARY_CHARS = 2000

# Ollama settings (local)
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "60"))

# Gemini settings (Google, external)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_TIMEOUT = float(os.environ.get("GEMINI_TIMEOUT", "20"))

# Instructions for the model
SYSTEM_PROMPT = (
    "You summarize search results for a Black history archive hub. "
    "Answer the user's question using ONLY the numbered sources provided. "
    "Cite sources with their number in square brackets, like [1] or [2]. "
    "Use the previous conversation only to understand what the question refers to; "
    "facts and citations must come from the numbered sources. "
    "Write 2 to 4 sentences. Answer in the same language as the question. "
    "If the sources do not answer the question, say that the records found "
    "do not cover it. Never invent names, dates or facts."
)

app = FastAPI(title="BCCNS Search API")


class Turn(BaseModel):
    """One earlier question and its answer."""
    question: str = Field(min_length=1, max_length=500)
    summary: str | None = Field(default=None, max_length=MAX_SUMMARY_CHARS)


# Checked filter values, e.g. {"contentcategory": ["people", "events"]}: only known fields,
# at most 20 values each, 1-200 characters
Filters = dict[
    FacetField,
    Annotated[list[Annotated[str, Field(min_length=1, max_length=200)]], Field(max_length=20)],
]


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=8, ge=1, le=20)
    provider: Literal["ollama", "gemini"] | None = None
    history: list[Turn] = Field(default_factory=list, max_length=3)  # oldest first
    filters: Filters = Field(default_factory=dict)
    # false = skip the AI: records and counts come back in milliseconds. The web app uses
    # this when a filter is clicked, then asks again with a summary once the clicking stops.
    summary: bool = True


class BrowseRequest(BaseModel):
    """Browsing without a question: the newest records, filtered, with counts."""
    limit: int = Field(default=12, ge=1, le=50)
    filters: Filters = Field(default_factory=dict)


class FacetsRequest(BaseModel):
    """One filter panel: the values of one field, with counts, for the same question and
    filters as the records on the page (same rules as SearchRequest)."""
    question: str = Field(min_length=1, max_length=500)
    history: list[Turn] = Field(default_factory=list, max_length=3)
    filters: Filters = Field(default_factory=dict)
    facet: FacetField  # the field whose values the panel lists
    search: str = Field(default="", max_length=100)  # text typed in the panel's search field
    sort: Literal["count", "alpha"] = "count"  # most records first, or A–Z
    limit: int = Field(default=8, ge=1, le=100)  # values per page
    cursor: str | None = Field(default=None, max_length=200)  # next_cursor of the previous page


def quote(value):
    """Put a value in double quotes for a Meilisearch filter, escaping \\ and " inside it,
    so a value can never end the quotes early and change the filter."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_filter(filters):
    """{"contentcategory": ["people", "events"], "attribution": ["BCCNS"]}
    → 'contentcategory IN ["people", "events"] AND attribution IN ["BCCNS"]'
    OR between values of one field, AND between fields. None = no filter."""
    parts = [
        f"{field} IN [{', '.join(quote(v) for v in values)}]"
        for field, values in filters.items()
        if values
    ]
    return " AND ".join(parts) or None


def with_filter(query, filters):
    """Copy of a Meilisearch query with the filter for `filters` added (none if empty)."""
    search_filter = build_filter(filters)
    return {**query, "filter": search_filter} if search_filter else dict(query)


def count_body(body):
    """A count search for `body`: ranks up to COUNT_LIMIT records (see there). Only the counts
    are used, so it returns just the id of each ranked record, to keep the answer small.
    (Not limit 0: that makes Meilisearch skip the meaning half of a hybrid search.)"""
    return {**body, "limit": COUNT_LIMIT, "attributesToRetrieve": ["id"], "showRankingScore": False}


def without_own_filter(filters, field):
    """Every filter except `field`'s own: its values are alternatives (OR), so they mustn't
    hide each other in the counts."""
    return {f: v for f, v in filters.items() if f != field}


def build_searches(body, filters):
    """The main search (the records shown), plus the searches that count the filter values.

    Counts never come from the main search: it ranks only `limit` (e.g. 8) records, and
    Meilisearch would then count weak matches below the threshold too (see COUNT_LIMIT).
    - one count search with ALL filters. It counts the fields WITHOUT checked values, and its
      hits are the total number of matching records (see total()). It is always there, even
      when every field has checked values (then it counts no field, only the total).
    - one count search per field WITH checked values, with every filter EXCEPT its own: with
      "people" checked, the category counts still show "history (7)". The values of one field
      are alternatives (OR), so checking one mustn't hide the others. Other fields still apply.
    Returns (searches, counted): searches[0] is the main one, searches[1] the one with all
    filters; searches[i + 1] counts the fields in counted[i] (counted[0] can be empty).
    """
    checked = [field for field, values in filters.items() if values]
    unchecked = [field for field in FACET_FIELDS if field not in checked]
    count = count_body(body)

    searches = [
        with_filter(body, filters),
        with_filter({**count, "facets": unchecked} if unchecked else count, filters),
    ]
    counted = [unchecked]
    for field in checked:
        searches.append(with_filter({**count, "facets": [field]}, without_own_filter(filters, field)))
        counted.append([field])
    return searches, counted


def search_text(question, history):
    """Earlier questions + the new one, so 'Was she pardoned?' still finds Viola Desmond."""
    previous = [turn.question for turn in history[-2:]]
    return " ".join(previous + [question])


def build_prompt(question, hits, history=()):
    """Conversation (if any) + numbered sources + the question, as one text."""
    blocks = []
    for number, hit in enumerate(hits[:SUMMARY_SOURCES], start=1):
        blocks.append(
            f"[{number}] {hit.get('title', '')}\n"
            # summary = full text; description (150-char teaser) only if a record has no summary
            f"{hit.get('summary') or hit.get('description') or ''}\n"
            f"Held by: {hit.get('attribution', 'unknown')}"
        )
    sources = "\n\n".join(blocks)

    context = ""
    if history:
        turns = "\n\n".join(
            f"Q: {turn.question}\nA: {turn.summary or '(no answer)'}" for turn in history
        )
        context = f"Previous conversation:\n\n{turns}\n\n"

    return f"{context}Sources:\n\n{sources}\n\nQuestion: {question}"


async def ask_ollama(prompt):
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.2},
    }
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        r = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
    r.raise_for_status()
    return r.json()["message"]["content"].strip()


async def ask_gemini(prompt):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )
    async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as client:
        r = await client.post(url, json=payload, headers={"x-goog-api-key": GEMINI_API_KEY})
    r.raise_for_status()
    parts = r.json()["candidates"][0]["content"]["parts"]
    return "".join(part.get("text", "") for part in parts).strip()


SENTENCE_END = re.compile(r"[.!?](?=\s)")


def trim(text):
    """Keep answers within MAX_SUMMARY_CHARS, cutting at a sentence end if possible."""
    if len(text) <= MAX_SUMMARY_CHARS:
        return text
    cut = text[:MAX_SUMMARY_CHARS]
    ends = [m.end() for m in SENTENCE_END.finditer(cut)]
    # Only cut at a sentence end if that keeps at least half the text
    if ends and ends[-1] >= MAX_SUMMARY_CHARS // 2:
        return cut[: ends[-1]]
    return cut.rstrip()


async def summarize(question, hits, provider, history=()):
    """Returns (summary, provider_used). Falls back to Ollama if Gemini fails."""
    if not hits:
        return None, None

    prompt = build_prompt(question, hits, history)

    if provider == "gemini":
        try:
            return trim(await ask_gemini(prompt)), "gemini"
        except Exception as error:
            logger.warning("Gemini failed, falling back to Ollama: %s", error)

    try:
        return trim(await ask_ollama(prompt)), "ollama"
    except Exception as error:
        logger.warning("Ollama failed: %s", error)
        return None, None


@app.get("/health")
def health():
    return {"status": "ok"}


def check_api_key(x_api_key):
    # compare_digest instead of ==: takes the same time however many characters match
    if not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")


def collect_facets(counted, count_results):
    """The counts from the count searches of build_searches(), as {field: {value: count}}."""
    facets = {}
    for fields, result in zip(counted, count_results):
        distribution = result.get("facetDistribution", {})
        for field in fields:
            facets[field] = distribution.get(field, {})
    return facets


async def meili_search(client, searches, threshold=None):
    """Run several searches in ONE request (Meilisearch /multi-search), all keeping only hits
    that score at least `threshold` (None = no threshold, e.g. browsing). Returns Meilisearch's
    answer for each search, in the same order: "hits" and the counts ("facetDistribution")."""
    queries = [
        {**search, "indexUid": "records"}
        | ({"rankingScoreThreshold": threshold} if threshold is not None else {})
        for search in searches
    ]
    r = await client.post(
        f"{MEILI_URL}/multi-search",
        json={"queries": queries},
        headers={"Authorization": f"Bearer {MEILI_SEARCH_KEY}"},
    )
    if r.status_code != 200:
        # Log Meilisearch's own message (e.g. "attribute X is not filterable"); the caller
        # only gets a generic error.
        logger.warning("Meilisearch error %s: %s", r.status_code, r.text[:500])
        raise HTTPException(status_code=502, detail="Search engine error")
    return r.json()["results"]


async def run_with_fallback(client, searches):
    """meili_search() with the strict SCORE_THRESHOLD first. If the main search (searches[0])
    finds nothing, EVERY search runs once more with FALLBACK_THRESHOLD, so the hits, the counts
    and the total always use the same threshold. /api/search and /api/facets both use this, so
    the counts in a filter panel always agree with the records on the page."""
    results = await meili_search(client, searches, SCORE_THRESHOLD)
    if not results[0]["hits"] and FALLBACK_THRESHOLD < SCORE_THRESHOLD:
        results = await meili_search(client, searches, FALLBACK_THRESHOLD)
    return results


def total(results):
    """How many records match the question and all filters: the hits of the count search with
    all filters (searches[1] of build_searches()). It ranks up to COUNT_LIMIT records, so the
    number is exact below 1000 and stops at 1000. Not estimatedTotalHits: like the counts, that
    would include weak matches below the threshold."""
    return len(results[1]["hits"])


def fold(text):
    """Text for matching, without case and accents: "Université" → "universite".
    NFKD splits "é" into "e" + an accent mark; the marks are then dropped."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def sort_options(options, sort, selected):
    """Panel order. "count": most records first, ties A–Z. "alpha": A–Z.
    Either way, values with 0 records go last (the panel shows them disabled), except checked
    ones: a checked value must stay reachable so it can be unchecked."""
    def last(option):
        return option["count"] == 0 and option["value"] not in selected

    if sort == "alpha":
        return sorted(options, key=lambda o: (last(o), fold(o["value"])))
    return sorted(options, key=lambda o: (last(o), -o["count"], fold(o["value"])))


# Paging. The cursor is the position of the next page, packed as base64 JSON ({"o": 8}).
# The caller only sends back what it got, it never computes one, so the format can change
# later (e.g. to the last value seen) without changing the web app.
def encode_cursor(offset):
    return base64.urlsafe_b64encode(json.dumps({"o": offset}).encode()).decode()


def decode_cursor(cursor):
    if not cursor:
        return 0
    try:
        offset = json.loads(base64.urlsafe_b64decode(cursor))["o"]
    except (binascii.Error, ValueError, KeyError, TypeError):
        offset = None
    if not isinstance(offset, int) or offset < 0:
        raise HTTPException(status_code=422, detail="Invalid cursor")
    return offset


@app.post("/api/search")
async def search(req: SearchRequest, x_api_key: str = Header(default="")):
    # 1. Check the API key
    check_api_key(x_api_key)

    # 2. Search Meilisearch (earlier questions help with "she", "it", etc.)
    #    Strict threshold first; if that finds nothing, one more try with the looser one
    #    (run_with_fallback). Filters, counts and total: see build_searches().
    body = {
        "q": search_text(req.question, req.history),
        "hybrid": {"embedder": "default", "semanticRatio": SEMANTIC_RATIO},
        "limit": req.limit,
        "showRankingScore": True,
    }
    searches, counted = build_searches(body, req.filters)
    async with httpx.AsyncClient(timeout=10) as client:
        results = await run_with_fallback(client, searches)
    hits = results[0]["hits"]
    facets = collect_facets(counted, results[1:])

    # 3. Summary: the request's choice, or the default (uses the filtered hits).
    #    Skipped when the caller only wants records and counts.
    summary, used = None, None
    if req.summary:
        provider = req.provider or SUMMARY_PROVIDER
        summary, used = await summarize(req.question, hits, provider, req.history)

    return {
        "summary": summary,
        "provider": used,
        "results": hits,
        "total": total(results),
        "facets": facets,
    }


@app.post("/api/browse")
async def browse(req: BrowseRequest, x_api_key: str = Header(default="")):
    """The newest records, filtered by the checked pills, plus the counts for the pills.
    No question, so no AI and no score threshold: Meilisearch's "placeholder search" (q = "")
    simply returns all records that pass the filters, here sorted newest first."""
    check_api_key(x_api_key)

    body = {"q": "", "sort": ["createdAtTs:desc"], "limit": req.limit}
    # Same counting as in search(): each field is counted without its own filter
    searches, counted = build_searches(body, req.filters)
    async with httpx.AsyncClient(timeout=10) as client:
        results = await meili_search(client, searches)

    return {
        "results": results[0]["hits"],
        "total": total(results),
        "facets": collect_facets(counted, results[1:]),
    }


@app.post("/api/facets")
async def facet_options(req: FacetsRequest, x_api_key: str = Header(default="")):
    """The values of ONE field for a filter panel, with counts, filtered by the text typed in
    the panel, sorted and paged. The counts are the same as in /api/search for the same
    question and filters: the field is counted without its own filter, with the same threshold."""
    check_api_key(x_api_key)

    # 1. The same main search as /api/search, but limit 1: it only decides which threshold
    #    applies (run_with_fallback), so the counts agree with the records on the page.
    body = {
        "q": search_text(req.question, req.history),
        "hybrid": {"embedder": "default", "semanticRatio": SEMANTIC_RATIO},
        "limit": 1,
        "attributesToRetrieve": ["id"],
    }
    searches = [
        with_filter(body, req.filters),
        # 2. The counts: this field without its own filter, like in build_searches()
        with_filter(
            {**count_body(body), "facets": [req.facet]},
            without_own_filter(req.filters, req.facet),
        ),
    ]
    # 3. Every value the field has in the whole archive, so values with 0 matches can still be
    #    listed (disabled). A placeholder search (no question): no threshold, so it runs as a
    #    separate request, at the same time as the others.
    every_value = {"q": "", "limit": 0, "facets": [req.facet]}
    async with httpx.AsyncClient(timeout=10) as client:
        results, archive = await asyncio.gather(
            run_with_fallback(client, searches),
            meili_search(client, [every_value]),
        )
    counts = results[1].get("facetDistribution", {}).get(req.facet, {})
    in_archive = archive[0].get("facetDistribution", {}).get(req.facet, {})

    # 4. Checked values always count as values, even if they no longer exist: they must stay
    #    visible so they can be unchecked.
    selected = req.filters.get(req.facet, [])
    values = {**dict.fromkeys(in_archive), **dict.fromkeys(counts), **dict.fromkeys(selected)}
    options = [{"value": value, "count": counts.get(value, 0)} for value in values]

    # 5. The panel's search text: case and accents don't matter ("univ" finds "Université")
    needle = fold(req.search.strip())
    if needle:
        options = [option for option in options if needle in fold(option["value"])]
    options = sort_options(options, req.sort, selected)

    # 6. One page
    start = decode_cursor(req.cursor)
    end = start + req.limit
    return {
        "options": options[start:end],
        # The checked values, whatever was typed: the panel pins them on top
        "selected": [{"value": value, "count": counts.get(value, 0)} for value in selected],
        "total_options": len(options),  # how many values match the search text, on all pages
        "next_cursor": encode_cursor(end) if end < len(options) else None,
    }
