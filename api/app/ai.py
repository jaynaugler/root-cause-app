"""Google AI Studio (Gemini) cleanup for fetched PDF records.

Takes the LLM-relevant fields of a raw pdf.py record and returns cleaned
values ({title, description, attribution, contentcategory}). Hard rules:
temperature 0 with a response schema, and the prompt forbids inventing
anything — the model only reshapes what is already there. The caller
(pdf.py) falls back to the raw record whenever this module raises.
"""

import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger("uvicorn.error")

# Keep the prompt bounded — the model writes a short description, not a
# transcript. (pdf.py caps the full text at 100k chars; this is the LLM input.)
MAX_INPUT_CHARS = 48_000
MAX_DESCRIPTION_CHARS = 2000  # same cap as the search-api answers

# Archive vocabulary for contentcategory. Only these pass validation.
CATEGORIES = ["people", "places", "events", "organizations", "publications", "history"]

SYSTEM_PROMPT = (
	"You clean metadata records for a Black history archive search hub. "
	"Write the cleaned record as JSON matching the requested schema. "
	"Use ONLY information contained in the provided data — if something is "
	"missing, return null. Never invent names, dates, places, events or "
	"facts. Keep the language of the text."
)

USER_INSTRUCTIONS = f"""Clean the record below.

Rules:
- title: use the record's metadata title if it is any good; otherwise take the
  document's heading or first meaningful line of the text. null if neither exists.
- description: 2 to 4 plain-text sentences summarizing the text. Repair OCR
  line-breaks and obvious OCR letter errors, and drop watermark, credit-line,
  navigation and page-number junk. No titles, no markdown, no newlines.
- attribution: the person or organization the resource comes from — prefer a
  stated source/credit line in the text, then the metadata author/creator.
  null if unknown.
- contentcategory: pick exactly one of: {", ".join(CATEGORIES)}.

Record:
"""

# OpenAPI subset enforced by the Gemini API itself (responseSchema).
RESPONSE_SCHEMA = {
	"type": "OBJECT",
	"properties": {
		"title": {"type": "STRING", "nullable": True},
		"description": {"type": "STRING", "nullable": True},
		"attribution": {"type": "STRING", "nullable": True},
		"contentcategory": {"type": "STRING", "enum": CATEGORIES},
	},
	"required": ["title", "description", "attribution", "contentcategory"],
}


def _optional(value) -> str | None:
	"""Whitespace-trim a model string; empty or non-string becomes None."""
	if not isinstance(value, str):
		return None
	value = value.strip()
	return value[:MAX_DESCRIPTION_CHARS] if value else None


async def clean_record(fields: dict) -> dict:
	"""Cleaned {title, description, attribution, contentcategory}. Raises on
	anything unusable (no key, HTTP error, malformed reply) so the caller can
	fall back to the raw record."""
	if not settings.gemini_api_key:
		raise RuntimeError("GEMINI_API_KEY is not set")

	record = {
		"title": fields.get("title"),
		"attribution": fields.get("attribution"),
		"author": fields.get("author"),
		"creator": fields.get("creator"),
		"subject": fields.get("subject"),
		"text": (fields.get("text") or "")[:MAX_INPUT_CHARS],
	}
	payload = {
		"system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
		"contents": [{"role": "user", "parts": [{"text": USER_INSTRUCTIONS + json.dumps(record)}]}],
		"generationConfig": {
			"temperature": 0,  # deterministic reshape of the given data only
			"responseMimeType": "application/json",
			"responseSchema": RESPONSE_SCHEMA,
		},
	}
	url = (
		"https://generativelanguage.googleapis.com/v1beta/models/"
		f"{settings.gemini_model}:generateContent"
	)
	async with httpx.AsyncClient(timeout=settings.gemini_timeout) as client:
		resp = await client.post(
			url, json=payload, headers={"x-goog-api-key": settings.gemini_api_key}
		)
	resp.raise_for_status()
	parts = resp.json()["candidates"][0]["content"]["parts"]
	cleaned = json.loads("".join(part.get("text", "") for part in parts))
	if not isinstance(cleaned, dict):
		raise TypeError("Gemini reply is not a JSON object")

	return {
		"title": _optional(cleaned.get("title")),
		"description": _optional(cleaned.get("description")),
		"attribution": _optional(cleaned.get("attribution")),
		# Anything outside the vocabulary would be invention: map it to None.
		"contentcategory": cleaned.get("contentcategory")
		if cleaned.get("contentcategory") in CATEGORIES
		else None,
	}
