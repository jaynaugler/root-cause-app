"""News-article support: one URL box (POST /resource-metadata) that accepts
PDFs (delegated to the PDF machinery) and HTML pages (extracted with
trafilatura → the same Gemini cleanup and hallucination gate as PDFs)."""

import logging
from http import HTTPStatus

import trafilatura
from fastapi import APIRouter, HTTPException

from app.ai import clean_record
from app.pdf import (
	_REQUEST_SLOTS,
	MAX_FULL_TEXT_CHARS,
	MAX_SUMMARY_CHARS,
	PdfUrlIn,
	_download,
	_record_from_pdf,
	_ser,
)

logger = logging.getLogger("uvicorn.error")

router = APIRouter(tags=["resource"])


@router.post("/resource-metadata")
async def resource_metadata(payload: PdfUrlIn) -> dict:
	"""/pdf-metadata for HTML pages; PDF URLs are transparently delegated."""
	async with _REQUEST_SLOTS:  # same bounded queue as the PDF endpoint
		data = await _download(str(payload.url))
		if data[:5] == b"%PDF-":
			return await _record_from_pdf(data, str(payload.url))
		return await _record_from_article(data, str(payload.url))


async def _record_from_article(html: bytes, link: str) -> dict:
	"""HTML → readable article text → cleaned record. A cleanup failure of any
	kind (no key, gate, timeout) returns the raw record — same rules as PDFs."""
	body = trafilatura.extract(html, include_comments=False, include_tables=True)
	if not body:
		raise HTTPException(
			HTTPStatus.UNPROCESSABLE_ENTITY, "Could not extract an article from that page."
		)
	body = " ".join(body.split())
	try:
		meta = trafilatura.extract_metadata(trafilatura.load_html(html))
		meta = meta.as_dict() if meta else {}
	except Exception:  # noqa: BLE001 — broken page metadata never blocks extraction
		meta = {}

	# Feed the model as much of the article as it can use; the raw record's
	# `description` (as in the PDF flow) holds what arrives before cleanup.
	text = body[:MAX_FULL_TEXT_CHARS]

	record = {
		"title": _ser(meta.get("title")) or None,
		"link": link,
		"sitelink": None,  # curator-supplied, like PDFs
		"description": text[:MAX_SUMMARY_CHARS],  # pre-clean teaser cap
		"summary": None,  # filled by the Gemini cleanup
		"attribution": _ser(meta.get("author")) or None,
		"resourceformat": "article",
		"contentcategory": None,
		"imgurl": None,  # og:image extraction comes later
		"status": None,
		"details": {
			"author": _ser(meta.get("author")),
			"sitename": _ser(meta.get("sitename")),
			"publishedDate": _ser(meta.get("date")),
			"pageCount": 1,
			"extra": {},
		},
	}

	try:
		cleaned = await clean_record(
			{
				"title": record["title"],
				"attribution": record["attribution"],
				"author": _ser(meta.get("author")),
				"creator": _ser(meta.get("sitename")),
				"subject": None,
				"text": text,
			}
		)
	except Exception as exc:  # noqa: BLE001 — cleanup must never kill the fetch
		logger.warning("Gemini cleanup failed, returning the raw record: %s", exc)
		return record

	# Only overwrite with non-null cleaned values — an unsure model never
	# erases data that came out of the page itself.
	return {**record, **{k: v for k, v in cleaned.items() if v is not None}}
