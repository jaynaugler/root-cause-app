"""Download a PDF by URL and return a resource record: extracted description,
title, attribution, plus detailed document metadata. No persistence."""

import asyncio
import logging
import shutil
from datetime import datetime
from http import HTTPStatus
from io import BytesIO

import httpx
import pypdfium2 as pdfium
import pytesseract
from fastapi import APIRouter, HTTPException
from PIL import Image, ImageOps
from pydantic import BaseModel, HttpUrl
from pypdf import PdfReader
from pypdf.errors import PdfReadError, PyPdfError

from app.ai import clean_record
from app.egress import zenrows_enabled, zenrows_get

router = APIRouter(tags=["pdf"])
logger = logging.getLogger("uvicorn.error")

MAX_BYTES = 10 * 1024 * 1024  # 10 MB
DOWNLOAD_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
MAX_SUMMARY_CHARS = 2000
MAX_FULL_TEXT_CHARS = 100_000  # extraction safety cap; ai.py bounds the model input
# OCR quality: images at low DPI (e.g. a full page flattened at 72 dpi, 612px)
# read poorly — upscale to ~2400px on the long side, and drop words tesseract
# isn't sure about (it will guess pseudo-words out of decorative textures).
TARGET_LONG_SIDE = 2400
OCR_DPI = 300
MIN_WORD_CONF = 60.0
# OCR pages whose text layer covers less than this fraction of the page — a
# scan with only a short watermark line (or nothing) falls below, a real text
# layer covers most of the page. Char count is not a good gate: watermarks can
# be long (bccns footers are ~185 chars), which a count of 40 would pass.
MIN_TEXT_AREA_RATIO = 0.15
# Cap concurrent /pdf-metadata handlers (512 MB container): each holds ~10 MB of
# file bytes during download and ~100+ MB of render/OCR state during extraction.
MAX_CONCURRENT_REQUESTS = 2
_REQUEST_SLOTS = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

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


def _text_layer_is_spare(document: pdfium.PdfDocument, index: int) -> bool:
	"""True when this page's text layer covers only a small fraction of the page
	(image-only, or a scan leaving just a watermark in the text layer)."""
	page = None
	textpage = None
	try:
		page = document[index]
		textpage = page.get_textpage()
		char_count = textpage.count_chars()
		if char_count <= 0:
			return True
		ink = 0.0
		for i in range(char_count):
			left, bottom, right, top = textpage.get_charbox(i, loose=False)
			ink += max(0.0, right - left) * max(0.0, top - bottom)
		width, height = page.get_size()
		return ink < MIN_TEXT_AREA_RATIO * width * height
	except pdfium.PdfiumError:
		return True
	finally:
		if textpage is not None:
			textpage.close()
		if page is not None:
			page.close()


def _extract_text(reader: PdfReader, data: bytes) -> list[str]:
	"""Extract document text up to the safety cap, using OCR for image-only pages
	and pages with only a spare text layer (e.g. a watermark on a scan)."""
	texts: list[str] = []
	# Degrade gracefully to text-layer-only when tesseract isn't installed.
	ocr_ready = shutil.which("tesseract") is not None
	document = None
	if ocr_ready:
		try:
			document = pdfium.PdfDocument(data)
		except pdfium.PdfiumError:
			pass
	cap = MAX_FULL_TEXT_CHARS
	try:
		for index, page in enumerate(reader.pages):
			text = page.extract_text() or ""
			if document is not None and _text_layer_is_spare(document, index):
				text = _ocr_page(document, index) or text
			texts.append(text)
			if sum(len(t) for t in texts) > cap:
				break
	except PyPdfError:
		pass  # unreadable/odd page content just means no summary
	finally:
		if document is not None:
			document.close()
	return texts


def _ocr_page(document: pdfium.PdfDocument, index: int) -> str:
	"""Render the complete page so OCR sees the same orientation and composition
	as a reader, including placed images, cropping, and page rotation. Rendered
	grayscale directly — a third of the bitmap memory, and tesseract runs on
	grayscale anyway."""
	page = None
	bitmap = None
	image = None
	try:
		page = document[index]
		scale = min(OCR_DPI / 72, TARGET_LONG_SIDE / max(page.get_size()))
		bitmap = page.render(scale=scale, grayscale=True)
		image = bitmap.to_pil()
		return _ocr(image)
	except pdfium.PdfiumError:
		return ""
	finally:
		if image is not None:
			image.close()
		if bitmap is not None:
			bitmap.close()
		if page is not None:
			page.close()


def _ocr(image) -> str:
	"""OCR one rendered page, trying each quarter-turn when the first read
	scores poorly. Contrast normalization helps faint scans; the render already
	arrives grayscale (mode L)."""
	image = ImageOps.autocontrast(image)
	long_side = max(image.width, image.height)
	if long_side < TARGET_LONG_SIDE:
		scale = max(1, min(4, round(TARGET_LONG_SIDE / long_side)))
		image = image.resize((image.width * scale, image.height * scale), Image.Resampling.LANCZOS)
	best, best_conf = "", -1.0
	for angle in (0, 90, 180, 270):
		rotated = image if angle == 0 else image.rotate(angle, expand=True)
		try:
			text, confidence = _read(rotated)
			if not text:
				continue
			if confidence > best_conf:
				best, best_conf = text, confidence
			if best_conf >= 80:  # clearly readable; no further rotations needed
				break
		finally:
			if rotated is not image:
				rotated.close()
	return best


def _read(image) -> tuple[str, float]:
	"""One OCR pass → (cleaned text, mean word confidence). Low-confidence
	words are dropped from the text; the mean over all real words still drives
	rotation selection."""
	try:
		data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
	except pytesseract.TesseractError:
		return "", -1.0
	words = [
		(w, float(c)) for w, c in zip(data["text"], data["conf"]) if w.strip() and float(c) >= 0
	]
	if not words:
		return "", -1.0
	mean_conf = sum(c for _, c in words) / len(words)
	text = " ".join(w for w, c in words if c >= MIN_WORD_CONF).strip()
	return text, mean_conf


def _summarize(texts: list[str], cap: int) -> str | None:
	joined = " ".join(" ".join(text.split()) for text in texts if text)
	return joined[:cap] or None


@router.post("/pdf-metadata")
async def pdf_metadata(payload: PdfUrlIn) -> dict:
	async with _REQUEST_SLOTS:  # bounded queue; waiters hold only the URL
		return await _run_pdf_metadata(payload)


async def _zenrows_download(url: str) -> bytes | None:
	"""PDF bytes through the ZenRows relay as a single buffered response.

	Returns None when the relay path is unusable (no key configured, relay
	failure or timeout, over the 10 MB cap, body not a PDF) so the caller can
	stream directly — a relay failure must not change what the endpoint answers,
	only which route the bytes took. A genuinely oversized relayed PDF still
	raises the cap error here: retrying it directly would just download it twice.
	"""
	if not zenrows_enabled():
		return None
	try:
		async with httpx.AsyncClient(
			follow_redirects=True, timeout=DOWNLOAD_TIMEOUT
		) as client:
			resp = await zenrows_get(client, url, headers={"user-agent": USER_AGENT})
		if resp is None:
			return None
		if resp.status_code != 200:
			logger.warning("ZenRows relay failed for %s (HTTP %d) — streaming directly", url, resp.status_code)
			return None
		if len(resp.content) > MAX_BYTES:
			raise HTTPException(HTTPStatus.CONTENT_TOO_LARGE, "PDF exceeds the 10 MB limit.")
		if not resp.content.startswith(b"%PDF-"):
			return None  # HTML block/error page or non-PDF body — let direct try
		return resp.content
	except (httpx.TimeoutException, httpx.HTTPError):
		logger.warning("ZenRows relay unreachable for %s — streaming directly", url)
		return None


async def _download_direct(payload: PdfUrlIn) -> bytes:
	chunks: list[bytes] = []
	size = 0
	try:
		async with httpx.AsyncClient(
			follow_redirects=True, timeout=DOWNLOAD_TIMEOUT
		) as client, client.stream("GET", str(payload.url), headers={"user-agent": USER_AGENT}) as resp:
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
	return b"".join(chunks)


async def _run_pdf_metadata(payload: PdfUrlIn) -> dict:
	# Relay first (Render's IP is blocked by several hosts): ZenRows returns the
	# body in one response, so its 10 MB cap is enforced after the fact. Anything
	# unusable there — no key, relay failure, oversized, non-PDF — falls through
	# to the direct streaming download, which enforces the cap during transfer.
	data = await _zenrows_download(str(payload.url))
	if data is None:
		data = await _download_direct(payload)

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

	record = {
		"title": _ser(title) or None,
		"link": str(payload.url),
		"sitelink": None,  # the site hosting this resource — curator fills it in
		"description": _summarize(
			_extract_text(reader, data=data),
			MAX_FULL_TEXT_CHARS,
		),
		"summary": None,  # full cleaned summary — filled by the Gemini cleanup
		"attribution": _ser(raw.get("/Author")) or _ser(raw.get("/Creator")) or None,
		"resourceformat": "pdf",
		"contentcategory": None,  # filled by the Gemini cleanup
		"imgurl": None,  # cover-image extraction comes later
		"status": None,  # stamped by the submit/approval flow at Mongo insert
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

	# Debug aid: the pre-clean record, so callers can diff raw vs cleaned.
	# The insert flow strips it exactly like `details`. Shallow copy is fine —
	# only top-level fields are later overwritten.
	record["raw"] = {k: v for k, v in record.items() if k != "raw"}

	# Clean the record with Gemini. Failure of any kind — no key, bad model
	# name, timeout, malformed reply — returns the raw record instead.
	try:
		cleaned = await clean_record(
			{
				"title": record["title"],
				"attribution": record["attribution"],
				"author": _ser(raw.get("/Author")),
				"creator": _ser(raw.get("/Creator")),
				"subject": _ser(raw.get("/Subject")),
				"text": record["description"],
			}
		)
	except Exception as exc:  # noqa: BLE001 — cleanup must never kill the fetch
		logger.warning("Gemini cleanup failed, returning the raw record: %s", exc)
		return record

	# Only overwrite with non-null cleaned values, so an unsure model never
	# erases data that came straight out of the document.
	return {**record, **{k: v for k, v in cleaned.items() if v is not None}}
