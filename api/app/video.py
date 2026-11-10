"""YouTube videos: fetch a public transcript and turn it into a resource record."""

import asyncio
import html
import logging
import os
import re
from http import HTTPStatus
from urllib.parse import parse_qs, quote, urlparse

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from youtube_transcript_api import (
	IpBlocked,
	NoTranscriptFound,
	PoTokenRequired,
	RequestBlocked,
	TranscriptsDisabled,
	VideoUnavailable,
	VideoUnplayable,
	YouTubeRequestFailed,
	YouTubeTranscriptApi,
	YouTubeTranscriptApiException,
)
from youtube_transcript_api.proxies import WebshareProxyConfig

from app.ai import clean_record
from app.pdf import _REQUEST_SLOTS

logger = logging.getLogger("uvicorn.error")
router = APIRouter(tags=["resource"])

# YouTube blocks transcript requests from datacenter IPs (Render), so the fetch needs
# an egress YouTube accepts — a residential proxy. All three YouTubeTranscriptApi
# proxy vars must be set (WebshareProxyConfig is the documented setup), and the api
# service needs them in its Render environment; without them we use the direct IP.
PROXY_USERNAME = os.environ.get("YT_PROXY_USERNAME")
PROXY_PASSWORD = os.environ.get("YT_PROXY_PASSWORD")


class _WebshareRotatingProxyConfig(WebshareProxyConfig):
	"""WebshareProxyConfig, but with URL-safe credentials.

	Its url builder interpolates the username and password raw, so a password
	containing a URL-special character ('#', '@', '?', …) cuts the proxy URL
	short and every fetch dies at parse time — Webshare passwords routinely
	contain such characters, which is why the proxy can appear "never wired up".
	Percent-encoding them fixes that without changing the rotating-residential
	behaviour the library expects (retries rotate to a new IP, keep-alive off)."""

	@property
	def url(self) -> str:
		username = self.proxy_username
		if username.endswith("-rotate"):
			username = username[: -len("-rotate")]
		return (
			f"http://{quote(username, safe='')}-rotate:{quote(self.proxy_password, safe='')}"
			f"@{self.domain_name}:{self.proxy_port}/"
		)


def _transcript_api() -> YouTubeTranscriptApi:
	"""The transcript client, through the Webshare proxy when it is configured.

	Logs which path every transcript fetch takes — when YouTube keeps refusing,
	the first thing to check in these logs is whether fetches went through the
	proxy at all (api/scripts/check_yt_proxy.py reproduces the chain locally)."""
	if PROXY_USERNAME and PROXY_PASSWORD:
		logger.info("transcript fetch: using the Webshare proxy configured in YT_PROXY_*")
		return YouTubeTranscriptApi(_WebshareRotatingProxyConfig(PROXY_USERNAME, PROXY_PASSWORD))
	logger.info("transcript fetch: NO proxy configured — using the server IP directly")
	return YouTubeTranscriptApi()

OEMBED_TIMEOUT = 10.0
TRANSCRIPT_EXCERPT_CHARS = 15_000  # three excerpts + metadata fit the AI input cap
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"


class VideoUrlIn(BaseModel):
	url: HttpUrl


def _video_id(payload_url: str) -> str:
	"""Accept normal watch, share, Shorts, Live, and embed YouTube URLs."""
	parsed = urlparse(payload_url)
	host = (parsed.hostname or "").lower()
	id = None
	if host == "youtu.be":
		id = parsed.path.strip("/").split("/")[0]
	elif host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
		if parsed.path == "/watch":
			id = (parse_qs(parsed.query).get("v") or [None])[0]
		else:
			match = re.match(r"^/(?:shorts|live|embed)/([^/]+)", parsed.path)
			id = match.group(1) if match else None
	if id and re.fullmatch(r"[A-Za-z0-9_-]{11}", id):
		return id
	raise HTTPException(
		HTTPStatus.UNPROCESSABLE_ENTITY,
		"Please paste a YouTube video URL, like https://www.youtube.com/watch?v=….",
	)


def _fetch_transcript(video_id: str) -> tuple[str, str]:
	"""Synchronous library call, run in a thread by the async endpoint."""
	api = _transcript_api()
	available = list(api.list(video_id))
	if not available:
		raise ValueError("This video has no available transcript.")
	# Prefer English and human-written captions, but don't reject other languages.
	transcript = min(
		available,
		key=lambda item: (not item.language_code.lower().startswith("en"), item.is_generated),
	)
	fetched = transcript.fetch()
	text = " ".join(html.unescape(snippet.text) for snippet in fetched.snippets)
	return re.sub(r"\s+", " ", text).strip(), fetched.language_code


def _transcript_excerpts(text: str) -> str:
	"""Use all of a short transcript, or labelled excerpts across a long one."""
	cap = TRANSCRIPT_EXCERPT_CHARS
	if len(text) <= cap * 3:
		return text
	parts = []
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
		parts.append(f"{label}:\n{chunk.strip()}")
	return "\n\n".join(parts)


async def _oembed(video_id: str) -> dict:
	url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
	try:
		async with httpx.AsyncClient(timeout=OEMBED_TIMEOUT, follow_redirects=True) as client:
			resp = await client.get(url, headers={"user-agent": USER_AGENT})
		return resp.json() if resp.status_code == 200 else {}
	except (httpx.HTTPError, ValueError):
		return {}


async def _record_from_video(video_id: str, metadata: dict, transcript: dict) -> dict:
	attribution = metadata.get("author_name") or None
	excerpts = _transcript_excerpts(transcript["text"])
	record = {
		"title": metadata.get("title") or None,
		"link": f"https://www.youtube.com/watch?v={video_id}",
		"sitelink": None,
		# A transcript is evidence for cleanup, not a ready-made card or summary.
		"description": None,
		"summary": None,
		"attribution": attribution,
		"resourceformat": "video",
		"contentcategory": None,
		"imgurl": metadata.get("thumbnail_url") or None,
		"status": None,
	}
	try:
		cleaned = await clean_record(
			{
				"title": record["title"],
				"attribution": attribution,
				"author": attribution,
				"creator": attribution,
				"subject": f"YouTube transcript ({transcript['language']})",
				"text": f"video transcript (full text or beginning/middle/end excerpts):\n{excerpts}",
			}
		)
	except Exception as exc:  # noqa: BLE001 — cleanup must never kill the fetch
		logger.warning("Gemini cleanup failed, returning the raw video record: %s", exc)
		return record
	return {**record, **{k: v for k, v in cleaned.items() if v is not None}}


@router.post("/video-metadata")
async def video_metadata(payload: VideoUrlIn) -> dict:
	async with _REQUEST_SLOTS:
		return await _run_video_metadata(payload)


def _transcript_message(exc: Exception) -> str:
	"""A message that says which thing went wrong, instead of one generic one."""
	if isinstance(exc, TranscriptsDisabled):
		return "This video has captions turned off, so there is no transcript to read."
	if isinstance(exc, NoTranscriptFound):
		return "No public transcript is available for this video."
	if isinstance(exc, (VideoUnavailable, VideoUnplayable)):
		return "That video is unavailable (it may be private, age-restricted or removed)."
	if isinstance(exc, (IpBlocked, RequestBlocked, PoTokenRequired, YouTubeRequestFailed)):
		# YouTube refusing this server (e.g. datacenter IP) is a server-side problem,
		# not a problem with the pasted link.
		return "YouTube is refusing transcript requests from our server right now — try again later."
	return "Could not retrieve a public transcript for this YouTube video."


async def _run_video_metadata(payload: VideoUrlIn) -> dict:
	video_id = _video_id(str(payload.url))
	metadata = await _oembed(video_id)
	try:
		text, language = await asyncio.to_thread(_fetch_transcript, video_id)
	except (YouTubeTranscriptApiException, ValueError) as exc:
		logger.warning(
			"Transcript fetch failed for %s: %s: %s", video_id, type(exc).__name__, exc
		)
		raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, _transcript_message(exc)) from exc
	if not text:
		raise HTTPException(HTTPStatus.UNPROCESSABLE_ENTITY, "The video's transcript is empty.")
	return await _record_from_video(video_id, metadata, {"text": text, "language": language})
