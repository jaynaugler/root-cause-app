"""Download a PDF by URL and return a resource record: extractable summary,
title, attribution, plus detailed document metadata. No persistence."""

import logging
import shutil
from datetime import datetime
from http import HTTPStatus
from io import BytesIO

import httpx
import pytesseract
from fastapi import APIRouter, HTTPException
from PIL import ImageOps
from pydantic import BaseModel, HttpUrl
from pypdf import PageObject, PdfReader
from pypdf.errors import PdfReadError, PyPdfError

router = APIRouter(tags=["pdf"])

MAX_BYTES = 10 * 1024 * 1024  # 10 MB
DOWNLOAD_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
SUMMARY_PAGES = 3
MAX_SUMMARY_CHARS = 2000
MAX_FULL_TEXT_CHARS = 100_000  # sanity cap when pulling a short doc's full text

# Metadata keys we shape into top-level response fields (compared lowercased).
KNOWN_FIELDS = {"title", "author", "subject", "creator", "producer", "creationdate", "moddate"}


class PdfUrlIn(BaseModel):
	url: HttpUrl  # enforces http/https scheme; invalid input → FastAPI 422


def _ser(value) -> str | None:
	if value is None:
		return None
	if isinstance(value, datetime):
		return value.isoformat()
	return str(value)


def _extract_text(reader: PdfReader, full: bool) -> list[str]:
	"""Text from the first few pages — the text layer, plus OCR of embedded
	images (scanned pages bury their real text in images, e.g. bccns PDFs).
	`full`: pull every page (single-page docs), not just the first few."""
	texts: list[str] = []
	# Degrad gracefully to text-layer-only when tesseract isn't installed.
	ocr_ready = shutil.which("tesseract") is not None
	cap = MAX_FULL_TEXT_CHARS if full else MAX_SUMMARY_CHARS
	try:
		pages = reader.pages if full else reader.pages[:SUMMARY_PAGES]
		for page in pages:
			parts = [page.extract_text() or ""]
			if ocr_ready:
				parts.append(_ocr_embedded_images(page, cap))
			texts.append(" ".join(p for p in parts if p))
			if sum(len(t) for t in texts) > cap:
				break
	except PyPdfError:
		pass  # unreadable/odd page content just means no summary
	return texts


def _ocr_embedded_images(page: PageObject, cap: int) -> str:
	out: list[str] = []
	try:
		images = list(page.images)
	except PyPdfError:
		return ""
	for image in images:
		text = None
		try:
			text = _ocr(image.image)
		except Exception as exc:  # noqa: BLE001 — an unreadable image just yields no text
			logging.getLogger(__name__).warning("OCR failed for an embedded image: %s", exc)
		if text:
			out.append(text)
		if sum(len(t) for t in out) > cap:
			break
	return " ".join(out)


def _ocr(image) -> str:
	"""OCR one image, retrying flipped/rotated placements when the first read
	scores poorly — pypdf extracts raw XObject bytes without the PDF's
	placement transform, so image content can come out mirrored."""
	best, best_conf = "", -1.0
	placements = (
		image,
		image.rotate(180),
		ImageOps.mirror(image),
		ImageOps.flip(image),
	)
	for img in placements:
		text = pytesseract.image_to_string(img).strip()
		if not text:
			continue
		confidence = _mean_word_confidence(img)
		if confidence > best_conf:
			best, best_conf = text, confidence
		if best_conf >= 80:  # clearly readable; no further placements needed
			break
	return best


def _mean_word_confidence(image) -> float:
	try:
		data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
	except pytesseract.TesseractError:
		return -1.0
	confs = [float(c) for c in data["conf"] if float(c) >= 0]
	return sum(confs) / len(confs) if confs else -1.0


def _summarize(texts: list[str], cap: int) -> str | None:
	joined = " ".join(" ".join(text.split()) for text in texts if text)
	return joined[:cap] or None


@router.post("/pdf-metadata")
async def pdf_metadata(payload: PdfUrlIn) -> dict:
	# Download (streaming so the 10 MB cap holds even without a content-length)
	chunks: list[bytes] = []
	size = 0
	try:
		async with httpx.AsyncClient(
			follow_redirects=True, timeout=DOWNLOAD_TIMEOUT
		) as client, client.stream("GET", str(payload.url)) as resp:
			if resp.status_code != 200:
				raise HTTPException(
					HTTPStatus.BAD_GATEWAY, f"Download failed with HTTP status {resp.status_code}."
				)
			declared = resp.headers.get("content-length")
			if declared and int(declared) > MAX_BYTES:
				raise HTTPException(HTTPStatus.CONTENT_TOO_LARGE, "PDF exceeds the 10 MB limit.")
			async for chunk in resp.aiter_bytes():
				size += len(chunk)
				if size > MAX_BYTES:
					raise HTTPException(HTTPStatus.CONTENT_TOO_LARGE, "PDF exceeds the 10 MB limit.")
				chunks.append(chunk)
	except httpx.TimeoutException:
		raise HTTPException(HTTPStatus.GATEWAY_TIMEOUT, "Timed out downloading the PDF.")
	except httpx.HTTPError:
		raise HTTPException(HTTPStatus.BAD_GATEWAY, "Could not download a file from that URL.")
	data = b"".join(chunks)

	# Sanity check: many hosts serve PDFs as application/octet-stream, so the
	# magic bytes are a more reliable gate than the content-type header.
	if not data.startswith(b"%PDF-"):
		raise HTTPException(
			HTTPStatus.UNPROCESSABLE_ENTITY, "That URL does not point to a PDF file."
		)

	# Parse; PageCount/decrypt failures surface here too, but HTTPExceptions
	# raised inside the try would be swallowed by this except — re-raise first.
	try:
		reader = PdfReader(BytesIO(data))
		if reader.is_encrypted and not reader.decrypt(""):
			raise HTTPException(
				HTTPStatus.UNPROCESSABLE_ENTITY, "The PDF is password-protected and cannot be read."
			)
		raw = dict(reader.metadata or {})
		created_at = reader.metadata.creation_date  # parsed datetime, or None
		modified_at = reader.metadata.modification_date
		page_count = len(reader.pages)
	except HTTPException:
		raise
	except PdfReadError:
		raise HTTPException(
			HTTPStatus.UNPROCESSABLE_ENTITY, "That file could not be parsed as a PDF."
		)

	# XMP often carries a title when /Info does not (modern Word/InDesign exports)
	title = raw.get("/Title")
	if not title:
		try:
			xmp = reader.xmp_metadata
			if xmp is not None:
				dc_title = xmp.dc_title
				title = dc_title[0] if dc_title else None
		except PyPdfError:
			pass

	# Single-page docs (e.g. the bccns info sheets): return their full text
	# instead of the capped first-pages summary.
	short_doc = page_count <= 1

	return {
		"title": _ser(title) or None,
		"link": str(payload.url),
		"summary": _summarize(
			_extract_text(reader, full=short_doc),
			MAX_FULL_TEXT_CHARS if short_doc else MAX_SUMMARY_CHARS,
		),
		"attribution": _ser(raw.get("/Author")) or _ser(raw.get("/Creator")) or None,
		"resourceformat": "pdf",
		"contentcategory": None,  # classification comes later
		"imgurl": None,  # cover-image extraction comes later
		"details": {
			"author": _ser(raw.get("/Author")),
			"subject": _ser(raw.get("/Subject")),
			"creator": _ser(raw.get("/Creator")),
			"producer": _ser(raw.get("/Producer")),
			"creationDate": _ser(created_at) or _ser(raw.get("/CreationDate")),
			"modDate": _ser(modified_at) or _ser(raw.get("/ModDate")),
			"pageCount": page_count,
			"extra": {
				k.lstrip("/"): _ser(v)
				for k, v in raw.items()
				if k.lstrip("/").lower() not in KNOWN_FIELDS
			},
		},
	}
