"""Project Gutenberg ebooks: POST /book-metadata takes a Gutenberg page URL
(https://www.gutenberg.org/ebooks/<id>), pulls the book's catalog record from
gutendex, and runs the same Gemini cleanup + hallucination gate as PDFs.

Self-contained: gutendex blocks non-browser user-agents, so this module sends
its own browser UA. Cleanup is grounded in both the catalog summary and the
book's plain text, with Gutenberg's packaging removed."""

import logging
import re
from http import HTTPStatus

import httpx
from fastapi import APIRouter, HTTPException

from app.ai import clean_record
from app.pdf import _REQUEST_SLOTS, MAX_SUMMARY_CHARS, PdfUrlIn, _ser

logger = logging.getLogger("uvicorn.error")

router = APIRouter(tags=["resource"])

GUTENBERG_ID = re.compile(r"/ebooks/(\d+)")
# gutendex's hanging endpoints make 15s waits catastrophic in batches —
# fall through to the gutenberg.org scrape quickly instead.
GUTENDEX_TIMEOUT = 8.0
TEXT_TIMEOUT = httpx.Timeout(30.0, connect=5.0)
MAX_BOOK_BYTES = 10 * 1024 * 1024
BOOK_EXCERPT_CHARS = 15_000  # three excerpts + metadata fit ai.py's 48k input cap
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"

# Gutenberg catalog titles carry artifacts the card shouldn't show: MARC
# subfield delimiters ("Title : $b a comedy...") and series date-ranges
# ("The Suppression ... : 1638-1870"). Meaningful subtitles stay.
_TITLE_ARTIFACTS = [
	(re.compile(r"\s*:\s*\$b\s*", re.IGNORECASE), ": "),
	(re.compile(r"\s*\(\d{4}\)\s*$"), ""),  # "(1638-1870)" suffix form
	(re.compile(r"[:;,]?\s*\d{4}\s*[–—-]\s*\d{0,4}\s*$"), ""),  # ": 1638-1870" suffix
]


def _clean_title(title: str) -> str:
	for pattern, replacement in _TITLE_ARTIFACTS:
		title = pattern.sub(replacement, title)
	# Main title only: a long subtitle after ':' / ';' is catalog blurb
	# ("Abolition Fanaticism in New York: Speech of a Runaway Slave ...").
	# An "Or," continuation ("Clotel; Or, The President's Daughter") or a
	# short genre tag ("A Novel") is part of the work's name and stays.
	parts = re.split(r"\s*[:;]\s+", title, maxsplit=1)
	if len(parts) == 2 and len(parts[1]) > 25 and not re.match(r"(?i)^or[,;]?\s", parts[1]):
		title = parts[0]
	return title.strip().strip(":;,")


def _book_id(payload_url: str) -> str:
	if match := GUTENBERG_ID.search(payload_url):
		return match.group(1)
	raise HTTPException(
		HTTPStatus.UNPROCESSABLE_ENTITY,
		"Please paste a Gutenberg ebook page URL, like https://www.gutenberg.org/ebooks/23.",
	)


@router.post("/book-metadata")
async def book_metadata(payload: PdfUrlIn) -> dict:
	"""Gutenberg page URL → cleaned resource record."""
	id = _book_id(str(payload.url))
	async with _REQUEST_SLOTS:  # shared bounded queue with the PDF endpoint
		book = await _gutendex(id) or await _scrape_page(id)
		if book is None:
			raise HTTPException(HTTPStatus.NOT_FOUND, f"No Gutenberg book with id {id}.")
		return await _record_from_book(id, book)


async def _gutendex(id: str) -> dict | None:
	"""The catalog entry via gutendex — title, authors, subjects, curated
	summaries, download formats. Returns None when gutendex is unreachable or
	mid-outage (its per-book and `?ids=` endpoints currently hang for every
	client; use the gutenberg.org page scrape in that case — see _scrape_page)."""
	url = f"https://gutendex.com/books/?ids={id}"
	try:
		async with httpx.AsyncClient(
			timeout=GUTENDEX_TIMEOUT, follow_redirects=True
		) as client:
			resp = await client.get(url, headers={"user-agent": USER_AGENT})
	except (httpx.TimeoutException, httpx.HTTPError):
		return None
	if resp.status_code != 200:
		return None
	try:
		results = resp.json().get("results") or []
	except ValueError:
		return None
	return results[0] if results else None


async def _scrape_page(id: str) -> dict | None:
	"""gutenberg.org fallback: title, author, cover image and text link from the
	ebook page's structured markup. There is no curated summary here, so cleanup
	uses the plain text instead. Returns None when the page has no headline."""
	try:
		async with httpx.AsyncClient(
			timeout=GUTENDEX_TIMEOUT, follow_redirects=True
		) as client:
			resp = await client.get(f"https://www.gutenberg.org/ebooks/{id}", headers={"user-agent": USER_AGENT})
	except (httpx.TimeoutException, httpx.HTTPError):
		return None
	if resp.status_code != 200:
		return None
	html = resp.text.strip()

	title = _tag(html, r'itemprop="headline"[^>]*>([^<]+)')
	if not title:
		return None
	return {
		"id": id,
		"title": title,
		"authors": (
			[{"name": _tag(html, r'itemprop="creator"[^>]*>([^<]+)')}]
			if _tag(html, r'itemprop="creator"[^>]*>([^<]+)')
			else []
		),
		"subjects": [],
		# Cover art lives at a stable cache path (twitter:image confirms it).
		"cover": _tag(html, r'content="(https://www\.gutenberg\.org/cache/epub/[^"]+\.cover\.medium\.jpg)"'),
		"formats": {"text/plain; charset=utf-8": f"https://www.gutenberg.org/ebooks/{id}.txt.utf-8"},
	}


def _tag(html: str, pattern: str) -> str | None:
	if match := re.search(pattern, html):
		return " ".join(match.group(1).split())
	return None


def _text_asset_candidates(book: dict, id: str) -> list[str]:
	"""Plain-text asset URLs in preference order: gutendex's text/plain entry,
	then the canonical cache path, then the .txt.utf-8 pattern (which 404s for
	some titles — every candidate is validity-checked downstream)."""
	seen: list[str] = []
	for key, value in (book.get("formats") or {}).items():
		if "text/plain" in key and value not in seen:
			seen.append(value)
	for candidate in (
		f"https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt",
		f"https://www.gutenberg.org/ebooks/{id}.txt.utf-8",
	):
		if candidate not in seen:
			seen.append(candidate)
	return seen


def _clean_book_text(body: str) -> str:
	"""Remove Project Gutenberg's license/header packaging from the work itself."""
	if marker := re.search(r"\*\*\*\s*START OF[^*]*\*\*\*", body):
		body = body[marker.end() :]
	if marker := re.search(r"\*\*\*\s*END OF[^*]*\*\*\*", body):
		body = body[: marker.start()]
	return re.sub(r"\s+", " ", body).strip()


def _text_excerpts(text: str) -> str:
	"""Use the whole short text, or labelled beginning/middle/end excerpts.

	A whole novel exceeds the cleanup model's input budget. Sampling across the
	work gives the summary actual content to draw on without pretending that the
	title page and contents are a summary.
	"""
	cap = BOOK_EXCERPT_CHARS
	if len(text) <= cap * 3:
		return text
	excerpts = []
	for label, start in (
		("Beginning", 0),
		("Middle", (len(text) - cap) // 2),
		("End", len(text) - cap),
	):
		chunk = text[start : start + cap]
		if start and (space := chunk.find(" ")) >= 0:
			chunk = chunk[space + 1 :]
		if start + cap < len(text) and (space := chunk.rfind(" ")) >= 0:
			chunk = chunk[:space]
		excerpts.append(f"{label}:\n{chunk.strip()}")
	return "\n\n".join(excerpts)


async def _book_text(candidates: list[str]) -> str:
	"""Download and clean a book's plain text; reject HTML error pages."""
	try:
		async with httpx.AsyncClient(timeout=TEXT_TIMEOUT, follow_redirects=True) as client:
			for text_url in candidates:
				try:
					async with client.stream(
						"GET", text_url, headers={"user-agent": USER_AGENT}
					) as resp:
						if resp.status_code != 200:
							continue
						chunks: list[bytes] = []
						total = 0
						too_large = False
						async for chunk in resp.aiter_bytes():
							chunks.append(chunk)
							total += len(chunk)
							if total > MAX_BOOK_BYTES:
								too_large = True
								break
					if too_large:
						logger.warning("book text exceeds %d bytes: %s", MAX_BOOK_BYTES, text_url)
						continue
					body = b"".join(chunks).decode("utf-8-sig", "replace")
					if re.match(r"\s*<(?:!doctype|html)\b", body, re.IGNORECASE):
						continue
					if text := _clean_book_text(body):
						return text
				except (httpx.TimeoutException, httpx.HTTPError):
					continue
	except (httpx.TimeoutException, httpx.HTTPError):
		pass
	return ""


async def _record_from_book(id: str, book: dict) -> dict:
	authors = [a.get("name", "") for a in (book.get("authors") or []) if a.get("name")]
	# gutendex exposes the cover as an image/jpeg format; the scrape path as `cover`.
	cover = book.get("cover")
	if cover is None:
		cover = next((v for k, v in (book.get("formats") or {}).items() if "image/jpeg" in k), None)
	attribution = ", ".join(authors) or None
	subjects = " / ".join(book.get("subjects") or [][:12])
	catalog_summary = re.sub(
		r"\s*\(This is an automatically generated summary\.\)\s*$",
		"",
		" ".join(s.replace("\r", " ").replace("\n", " ") for s in book.get("summaries") or []),
		flags=re.IGNORECASE,
	)[:MAX_SUMMARY_CHARS]

	# Always ground cleanup in the book itself, even when the catalog has a
	# curated summary. Long books are represented by labelled excerpts across
	# the work rather than by front matter alone.
	book_text = _text_excerpts(await _book_text(_text_asset_candidates(book, id)))
	sources = []
	if catalog_summary:
		sources.append(f"catalog summary:\n{catalog_summary}")
	if book_text:
		sources.append(f"book text (full text or beginning/middle/end excerpts):\n{book_text}")
	given = (
		f"title: {book.get('title') or ''}\nauthor: {attribution or ''}\nsubjects: {subjects}\n"
		+ "\n".join(sources)
	)
	logger.info("book %s: %d chars of plain text available for cleanup", id, len(book_text))

	title = _ser(book.get("title"))
	record = {
		"title": _clean_title(title) if title else None,
		# The readable book page IS the link a human follows (card "Go!" button);
		# the raw text asset is derivable (/ebooks/<id>.txt.utf-8) and kept off
		# the record — same reason PDFs link their file but books link their page.
		"link": f"https://www.gutenberg.org/ebooks/{id}",
		"sitelink": None,  # hosting site is implicit for Gutenberg books
		# Only a curated catalog summary is a safe raw fallback. Book excerpts
		# are evidence for cleanup, not a summary, and must not leak into cards/search.
		"description": catalog_summary or None,
		"summary": None,
		"attribution": attribution,
		"resourceformat": "book",
		"contentcategory": None,
		"imgurl": _ser(cover) or None,  # card cover — free from either source
		"status": None,
		"details": {
			"author": attribution,
			"sitename": "Project Gutenberg",
			"publishedDate": None,
			"pageCount": 1,
			"extra": {
				"birth_year": _ser((book.get("authors") or [{}])[0].get("birth_year")),
				"death_year": _ser((book.get("authors") or [{}])[0].get("death_year")),
			},
		},
	}

	try:
		cleaned = await clean_record(
			{
				"title": record["title"],
				"attribution": attribution,
				"author": attribution,
				"creator": None,  # Gutenberg distributes it — it must not become the attribution
				"subject": subjects or None,
				"text": given,
			}
		)
	except Exception as exc:  # noqa: BLE001 — cleanup must never kill the fetch
		logger.warning("Gemini cleanup failed, returning the raw record: %s", exc)
		return record

	return {**record, **{k: v for k, v in cleaned.items() if v is not None}}
