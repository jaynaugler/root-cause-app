"""Download a PDF by URL and return its metadata. No persistence."""

from datetime import datetime
from http import HTTPStatus
from io import BytesIO

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from pypdf import PdfReader
from pypdf.errors import PdfReadError

router = APIRouter(tags=["pdf"])

MAX_BYTES = 10 * 1024 * 1024  # 10 MB
DOWNLOAD_TIMEOUT = httpx.Timeout(15.0, connect=5.0)

# Metadata keys we shape into top-level response fields (compared lowercased).
KNOWN_FIELDS = {"title", "author", "subject", "creator", "producer", "creationdate", "moddate"}

# pypdf's dict access returns raw "D:..." strings for dates; the
# creation_date/modification_date properties parse them into datetimes.
DATE_FIELDS = {"/CreationDate", "/ModDate"}


class PdfUrlIn(BaseModel):
	url: HttpUrl  # enforces http/https scheme; invalid input → FastAPI 422


def _ser(value) -> str | None:
	if value is None:
		return None
	if isinstance(value, datetime):
		return value.isoformat()
	return str(value)


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

	meta = {
		"title": _ser(raw.get("/Title")),
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
	}
	return meta
