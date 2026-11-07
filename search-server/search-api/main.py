import logging
import os
import secrets
from typing import Literal

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn.error")

# Meilisearch settings
MEILI_URL = os.environ.get("MEILI_URL", "http://meilisearch:7700")
MEILI_SEARCH_KEY = os.environ["MEILI_SEARCH_KEY"]
API_KEY = os.environ["API_KEY"]
SEMANTIC_RATIO = float(os.environ.get("SEMANTIC_RATIO", "0.5"))
SCORE_THRESHOLD = float(os.environ.get("SCORE_THRESHOLD", "0.6"))

# Summary settings
SUMMARY_PROVIDER = os.environ.get("SUMMARY_PROVIDER", "ollama")
SUMMARY_SOURCES = int(os.environ.get("SUMMARY_SOURCES", "5"))

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
    summary: str | None = Field(default=None, max_length=2000)


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=8, ge=1, le=20)
    provider: Literal["ollama", "gemini"] | None = None
    history: list[Turn] = Field(default_factory=list, max_length=3)  # oldest first


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
            f"{hit.get('description', '')}\n"
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


async def summarize(question, hits, provider, history=()):
    """Returns (summary, provider_used). Falls back to Ollama if Gemini fails."""
    if not hits:
        return None, None

    prompt = build_prompt(question, hits, history)

    if provider == "gemini":
        try:
            return await ask_gemini(prompt), "gemini"
        except Exception as error:
            logger.warning("Gemini failed, falling back to Ollama: %s", error)

    try:
        return await ask_ollama(prompt), "ollama"
    except Exception as error:
        logger.warning("Ollama failed: %s", error)
        return None, None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/search")
async def search(req: SearchRequest, x_api_key: str = Header(default="")):
    # 1. Check the API key
    if not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # 2. Search Meilisearch (earlier questions help with "she", "it", etc.)
    body = {
        "q": search_text(req.question, req.history),
        "hybrid": {"embedder": "default", "semanticRatio": SEMANTIC_RATIO},
        "limit": req.limit,
        "rankingScoreThreshold": SCORE_THRESHOLD,
        "showRankingScore": True,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{MEILI_URL}/indexes/records/search",
            json=body,
            headers={"Authorization": f"Bearer {MEILI_SEARCH_KEY}"},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Search engine error")
    hits = r.json()["hits"]

    # 3. Summary: the request's choice, or the default
    provider = req.provider or SUMMARY_PROVIDER
    summary, used = await summarize(req.question, hits, provider, req.history)

    return {"summary": summary, "provider": used, "results": hits}
