"""Google AI Studio (Gemini) cleanup for fetched PDF records.

Takes the LLM-relevant fields of a raw pdf.py record and returns cleaned
values ({title, description, attribution, contentcategory}). Hard rules:
temperature 0 with a response schema, the prompt forbids inventing anything,
and a deterministic gate verifies that years and proper names in the reply
were actually given to the model (one retry on violation, then the caller
falls back to the raw record — e.g. the "national historical person" upgrade
of a source's "national hero" wording would be caught by the gate).
"""

import json
import logging
import re

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
	"facts. Use names, titles and designations exactly as the record words "
	"them — never swap in a more official-sounding one you may recognize. "
	"Keep the language of the text."
)

USER_INSTRUCTIONS = f"""Clean the record below.

Rules:
- title: use the record's metadata title if it is any good; otherwise take the
  document's heading or first meaningful line of the text, minus generic labels
  like 'info sheet' or 'fact sheet'. null if neither exists.
- description: 2 to 4 plain-text sentences summarizing the text. Repair OCR
  line-breaks and obvious OCR letter errors, and drop watermark, credit-line,
  navigation and page-number junk. No titles, no markdown, no newlines.
- attribution: the person or organization the resource comes from. Prefer the
  document's own credit line — wording like "Source: X", "please credit: X",
  "© X", "courtesy of X" — over the metadata author/creator, which may name
  only the individual author. null if unknown.
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

# Capitalized words that are grammar, not names — sentence starters included.
_CAPS_STOP = {
	"the", "a", "an", "she", "he", "it", "they", "we", "i", "ii", "iii",
	"in", "on", "at", "by", "as", "of", "for", "and", "or", "nor", "but",
	"if", "so", "then", "after", "before", "when", "while", "during",
	"since", "until", "because", "though", "although", "later",
	"born", "its", "her", "his", "their", "this", "that", "these", "those",
	"there", "here", "among", "between", "both", "over", "under", "from",
	"into", "upon", "with", "within", "without", "through", "across",
	"against", "around", "toward", "towards", "despite", "however",
	"meanwhile", "also", "again", "once", "first", "next", "finally",
	"ultimately", "today", "some", "such", "one", "two", "three", "several",
	"many", "most", "much", "either", "beyond", "besides", "each", "every",
}


def _unsupported_phrases(text: str | None, model_input: str) -> list[str]:
	"""Deterministic hallucination gate: numbers, capitalized names/titles, and
	designation-adjective morphs in `text` that the model was never given.
	Offenders are returned for a retry with feedback; a second violation aborts
	the cleanup. Honest paraphrase (different verbs, e.g. 'achieved' for
	'achieve') passes; rewording a term into an official-sounding variant
	("historic" → "historical") does not."""
	if not text:
		return []
	given = _normalize(model_input)
	given_numbers = {
		re.sub(r"[^0-9]", "", number) for number in re.findall(r"\d[\d,]*", model_input)
	}
	problems: list[str] = []

	for number in re.findall(r"\d[\d,]*", text):
		digits = re.sub(r"[^0-9]", "", number)
		if digits and digits not in given_numbers:
			# "1940s" derived from a given "1941" is compression, not invention.
			if len(digits) == 4 and digits.endswith("0") and any(
				given.startswith(digits[:3]) and len(given) == 4 for given in given_numbers
			):
				continue
			problems.append(f"the figure {number}")

	def flush(run: list[str]) -> None:
		if len(run) >= 2:
			phrase = _normalize(" ".join(run))
			# A missing composite whose every word was given is paraphrase, not invention.
			if phrase not in given and any(_key(word) not in given for word in run):
				problems.append(" ".join(run))
		elif run and _key(run[0]) not in given:
			problems.append(run[0])
		run.clear()

	# The observed leak shape: "historic" → "historical" — a source adjective
	# rewritten into its more official-sounding form. Flag an absent word that
	# ends in an adjective morph and whose stem is a given WORD (whole word,
	# so "performing" can't match "perform" by prefix slicing).
	given_words = set(given.split())
	for word in re.findall(r"[a-z][a-z'’-]{6,}\b", text):
		if _key(word) in given:
			continue
		for suffix in ("ically", "ical", "al"):
			if not word.endswith(suffix):
				continue
			stem = _key(word[: -len(suffix)])
			if len(stem) >= 6 and any(
				given_word.startswith(stem) and len(given_word) - len(stem) <= 3
				for given_word in given_words
			):
				problems.append(f"'{word}' — the record words it as '{stem}…'")
			break

	for sentence in re.split(r"(?<=[.!?])\s+", text):
		run: list[str] = []
		for token in re.findall(r"[A-Za-z][\w'’-]*", sentence):
			if token[:1].isupper() and _key(token) not in _CAPS_STOP:
				run.append(token)
			else:
				flush(run)
		flush(run)
	return problems


def _key(word: str) -> str:
	"""Normalized keyword for the gate (lowercase, alphanumeric words only)."""
	return " ".join(re.findall(r"[a-z0-9]+", word.casefold()))


def _normalize(text: str) -> str:
	"""Casing/punctuation-insensitive form, so quoted phrases match the given data."""
	return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def _optional(value) -> str | None:
	"""Whitespace-trim a model string; empty or non-string becomes None."""
	if not isinstance(value, str):
		return None
	value = value.strip()
	return value[:MAX_DESCRIPTION_CHARS] if value else None


def _claims_problems(cleaned: dict, given_text: str) -> list[str]:
	"""Gate every model-authored free-text field against what the model received."""
	problems: list[str] = []
	for field in ("title", "description", "attribution"):
		problems += _unsupported_phrases(_optional(cleaned.get(field)), given_text)
	return problems


async def _generate(payload: dict) -> dict:
	"""One generateContent call → parsed JSON object; raises on any failure."""
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
	return cleaned


async def clean_record(fields: dict) -> dict:
	"""Cleaned {title, description, attribution, contentcategory}. Raises on
	anything unusable (no key, HTTP error, malformed reply, unsupported claims
	surviving the retry) so the caller can fall back to the raw record."""
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
	# The gate checks against exactly what was sent — this string, and nothing else.
	given_text = USER_INSTRUCTIONS + json.dumps(record)
	payload = {
		"system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
		"contents": [{"role": "user", "parts": [{"text": given_text}]}],
		"generationConfig": {
			"temperature": 0,  # deterministic reshape of the given data only
			"responseMimeType": "application/json",
			"responseSchema": RESPONSE_SCHEMA,
		},
	}

	# Hallucination gate: two attempts max. Offenders are fed back; a retry
	# that still fails raises → the caller returns the raw record.
	for attempt in range(2):
		cleaned = await _generate(payload)
		offenders = _claims_problems(cleaned, given_text)
		if not offenders:
			break
		logger.warning("Gemini cleanup used unsupported claims: %s", offenders)
		payload["contents"] += [
			{"role": "model", "parts": [{"text": json.dumps(cleaned)}]},
			{
				"role": "user",
				"parts": [{
					"text": (
						"Your reply used wording that is not in the provided data: "
						f"{offenders}. Rewrite the affected fields using only the "
						"provided wording — if none exists for a claim, drop it. "
						"Reply with the full corrected JSON."
					)
				}],
			},
		]
	else:
		raise TypeError(f"Unsupported claims in the cleaned record: {offenders}")

	return {
		"title": _optional(cleaned.get("title")),
		"description": _optional(cleaned.get("description")),
		"attribution": _optional(cleaned.get("attribution")),
		# Anything outside the vocabulary would be invention: map it to None.
		"contentcategory": cleaned.get("contentcategory")
		if cleaned.get("contentcategory") in CATEGORIES
		else None,
	}
