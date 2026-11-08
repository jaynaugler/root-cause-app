import logging
import os
import re
import secrets
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


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=8, ge=1, le=20)
    provider: Literal["ollama", "gemini"] | None = None
    history: list[Turn] = Field(default_factory=list, max_length=3)  # oldest first
    # {"contentcategory": ["people", "events"]}: only known fields, at most 20 short values each
    filters: dict[
        FacetField,
        Annotated[list[Annotated[str, Field(min_length=1, max_length=200)]], Field(max_length=20)],
    ] = Field(default_factory=dict)
    # false = skip the AI: records and counts come back in milliseconds. The web app uses
    # this when a filter is clicked, then asks again with a summary once the clicking stops.
    summary: bool = True


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


def build_searches(body, filters):
    """The main search (the records shown), plus the searches that count the filter values.

    Counts never come from the main search: it ranks only `limit` (e.g. 8) records, and
    Meilisearch would then count weak matches below the threshold too (see COUNT_LIMIT).
    - one count search for all fields WITHOUT checked values, with all filters
    - one count search per field WITH checked values, with every filter EXCEPT its own: with
      "people" checked, the category counts still show "history (7)". The values of one field
      are alternatives (OR), so checking one mustn't hide the others. Other fields still apply.
    Returns (searches, counted): searches[0] is the main one; searches[i + 1] counts the
    fields in counted[i].
    """
    checked = [field for field, values in filters.items() if values]
    unchecked = [field for field in FACET_FIELDS if field not in checked]
    # Only the counts are used: return just the id of each ranked record, to keep it small.
    # (Not limit 0: that makes Meilisearch skip the meaning half of a hybrid search.)
    count = {**body, "limit": COUNT_LIMIT, "attributesToRetrieve": ["id"], "showRankingScore": False}

    searches = [with_filter(body, filters)]
    counted = []
    if unchecked:
        searches.append(with_filter({**count, "facets": unchecked}, filters))
        counted.append(unchecked)
    for field in checked:
        other_filters = {f: v for f, v in filters.items() if f != field}
        searches.append(with_filter({**count, "facets": [field]}, other_filters))
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


async def meili_search(client, searches, threshold):
    """Run several searches in ONE request (Meilisearch /multi-search), all keeping only hits
    that score at least `threshold`. Returns Meilisearch's answer for each search, in the
    same order: "hits" and the facet counts ("facetDistribution")."""
    queries = [
        {**search, "indexUid": "records", "rankingScoreThreshold": threshold}
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


@app.post("/api/search")
async def search(req: SearchRequest, x_api_key: str = Header(default="")):
    # 1. Check the API key
    if not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # 2. Search Meilisearch (earlier questions help with "she", "it", etc.)
    #    Strict threshold first; if that finds nothing, one more try with the looser one.
    #    Filters and counts: see build_searches().
    body = {
        "q": search_text(req.question, req.history),
        "hybrid": {"embedder": "default", "semanticRatio": SEMANTIC_RATIO},
        "limit": req.limit,
        "showRankingScore": True,
    }
    searches, counted = build_searches(body, req.filters)
    async with httpx.AsyncClient(timeout=10) as client:
        results = await meili_search(client, searches, SCORE_THRESHOLD)
        if not results[0]["hits"] and FALLBACK_THRESHOLD < SCORE_THRESHOLD:
            # The count searches are re-run too: hits and counts use the same threshold
            results = await meili_search(client, searches, FALLBACK_THRESHOLD)
    hits = results[0]["hits"]
    # Collect the counts from the count searches (see build_searches)
    facets = {}
    for fields, result in zip(counted, results[1:]):
        distribution = result.get("facetDistribution", {})
        for field in fields:
            facets[field] = distribution.get(field, {})

    # 3. Summary: the request's choice, or the default (uses the filtered hits).
    #    Skipped when the caller only wants records and counts.
    summary, used = None, None
    if req.summary:
        provider = req.provider or SUMMARY_PROVIDER
        summary, used = await summarize(req.question, hits, provider, req.history)

    return {"summary": summary, "provider": used, "results": hits, "facets": facets}
