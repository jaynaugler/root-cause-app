"""Admin-managed RSS/Atom feeds whose recent entries become pending resources."""

import html
import logging
import re
from datetime import UTC, datetime

import feedparser
import httpx
from fastapi import APIRouter
from pydantic import BaseModel, HttpUrl

from app.ai import MIN_SUMMARY_CHARS, _description, clean_record
from app.db import db

logger = logging.getLogger("uvicorn.error")
router = APIRouter(tags=["feeds"])

MAX_ITEMS_PER_FEED = 10
FEED_TIMEOUT = httpx.Timeout(20.0, connect=5.0)
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
DEFAULT_FEEDS = [
	{
		"title": "Black communities — Canada.ca",
		"url": "https://api.io.canada.ca/io-server/gc/news/en/v2?audience=blackcommunities&sort=publishedDate&orderBy=desc&publishedDate%3E=2021-10-25&pick=100&format=atom&atomtitle=black%20communities",
	},
	{
		"title": "Strong and Free — Historica Canada",
		"url": "https://feeds.transistor.fm/strong-and-free",
	},
]


class FeedUrlIn(BaseModel):
	url: HttpUrl


def _plain_text(value) -> str:
	"""Feed summaries are often HTML; retain only their text."""
	if not isinstance(value, str):
		return ""
	return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def _image(entry: dict, feed: dict) -> str | None:
	for value in (entry.get("itunes_image"), entry.get("image"), feed.get("image")):
		if isinstance(value, dict) and (url := value.get("href") or value.get("url")):
			return url
	return None


async def _record_from_entry(entry: dict, feed: dict) -> dict | None:
	page_url = entry.get("link")
	if not page_url:
		return None
	enclosures = entry.get("enclosures") or []
	audio = next(
		(item.get("href") for item in enclosures if "audio" in item.get("type", "")), None
	)
	text = _plain_text(
		entry.get("itunes_summary")
		or entry.get("summary")
		or ((entry.get("content") or [{}])[0].get("value"))
	)
	feed_title = feed.get("title") or "RSS feed"
	attribution = entry.get("author") or feed.get("author") or None
	record = {
		"title": entry.get("title") or None,
		"link": audio or page_url,
		"sitelink": page_url if audio else None,
		"description": _description(text),
		"summary": text if len(text) >= MIN_SUMMARY_CHARS else None,
		"attribution": attribution,
		"resourceformat": "podcast" if audio else "article",
		"contentcategory": None,
		"imgurl": _image(entry, feed),
		"status": "pending",
		"createdAt": datetime.now(UTC),
	}
	try:
		cleaned = await clean_record(
			{
				"title": record["title"],
				"attribution": attribution,
				"author": attribution,
				"creator": attribution,
				"subject": feed_title,
				"text": text,
			}
		)
	except Exception as exc:  # noqa: BLE001 — retain the raw feed entry for review
		logger.warning("Gemini cleanup failed for feed entry %s: %s", page_url, exc)
		return record
	return {**record, **{k: v for k, v in cleaned.items() if v is not None}}


async def _feeds() -> list[dict]:
	collection = db["feeds"]
	for feed in DEFAULT_FEEDS:
		await collection.update_one(
			{"url": feed["url"]},
			{"$setOnInsert": {**feed, "createdAt": datetime.now(UTC)}},
			upsert=True,
		)
	return await collection.find().sort("createdAt", 1).to_list(length=100)


@router.get("/feeds")
async def list_feeds() -> dict:
	feeds = await _feeds()
	return {"success": True, "feeds": [{"id": str(f["_id"]), "title": f["title"], "url": f["url"]} for f in feeds]}


@router.post("/feeds")
async def add_feed(payload: FeedUrlIn) -> dict:
	url = str(payload.url)
	feeds = db["feeds"]
	result = await feeds.update_one(
		{"url": url},
		{"$setOnInsert": {"title": url, "url": url, "createdAt": datetime.now(UTC)}},
		upsert=True,
	)
	return {"success": True, "added": result.upserted_id is not None}


@router.post("/feeds/check")
async def check_feeds() -> dict:
	feeds = await _feeds()
	resources = db["resources"]
	for kind in ("article", "podcast"):
		await resources.create_index(
			"link",
			unique=True,
			partialFilterExpression={"resourceformat": kind},
			name=f"unique_{kind}_link",
		)
	result = {"inserted": 0, "duplicates": 0, "failed": []}
	checked = 0
	async with httpx.AsyncClient(timeout=FEED_TIMEOUT, follow_redirects=True) as client:
		for source in feeds:
			try:
				resp = await client.get(source["url"], headers={"user-agent": USER_AGENT})
				resp.raise_for_status()
			except httpx.HTTPError as exc:
				result["failed"].append({"feed": source["url"], "error": str(exc)[:200]})
				continue
			parsed = feedparser.parse(resp.content)
			checked += 1
			feed = parsed.feed
			if title := feed.get("title"):
				await db["feeds"].update_one({"_id": source["_id"]}, {"$set": {"title": title}})
			for entry in parsed.entries[:MAX_ITEMS_PER_FEED]:
				try:
					page_url = entry.get("link")
					if not page_url:
						continue
					enclosures = entry.get("enclosures") or []
					urls = [page_url] + [item["href"] for item in enclosures if item.get("href")]
					existing = await resources.find_one(
						{"$or": [{"link": {"$in": urls}}, {"sitelink": {"$in": urls}}]},
						{"_id": 1},
					)
					if existing:
						result["duplicates"] += 1
						continue
					record = await _record_from_entry(entry, feed)
					if not record:
						continue
					# Atomic upsert + the per-format unique index prevent duplicate
					# pending records even when two admins check feeds concurrently.
					stored = await resources.update_one(
						{"resourceformat": record["resourceformat"], "link": record["link"]},
						{"$setOnInsert": record},
						upsert=True,
					)
					if stored.upserted_id is None:
						result["duplicates"] += 1
					else:
						result["inserted"] += 1
				except Exception as exc:  # noqa: BLE001 — one entry must not stop the feed
					logger.warning("Could not import feed entry %s: %s", page_url, exc)
					result["failed"].append({"feed": source["url"], "error": str(exc)[:200]})
	return {"success": True, "feedsChecked": checked, **result}
