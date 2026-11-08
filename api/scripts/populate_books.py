"""Populate the `resources` collection with Project Gutenberg books.

Sources: a Gutenberg bookshelf and a subject page (walked for pagination),
unioned and deduped against what's already in the collection. Each book runs
through the same pipeline as the submit form (gutendex → page-scrape fallback
→ Gemini cleanup + gate), inserts with status 'approved', and skips records
without a downloadable text link (e.g. audio-only entries).

Usage (from api/):
  uv run python scripts/populate_books.py --db local            # or atlas
  uv run python scripts/populate_books.py --db local --reseed   # replace books only
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # api/ root, so `app` imports

import argparse
import asyncio
import json
import re
from datetime import UTC, datetime

import httpx

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
AI_CONCURRENCY = 1  # parallel cleanup calls exceed AI Studio's free-tier rate limit

LIST_URLS = [
	"https://www.gutenberg.org/ebooks/bookshelf/6",  # African American Writers
	"https://www.gutenberg.org/ebooks/subject/52",  # African Americans -- History
]

# Catalog artifacts, not resources: Gutenberg's own index pages ("by Various").
SKIP_TITLE_PATTERNS = [
	re.compile(r"^Index of Project Gutenberg", re.IGNORECASE),
]


def walk_listing(client: httpx.Client, url: str) -> set[str]:
	"""Book ids from a listing pages, following start_index pagination. The
	pager link stays on the page it points to, so visited URLs must be
	tracked or this walks the same page forever."""
	visited: set[str] = set()

	def recurse(page_url: str) -> set[str]:
		if page_url in visited:
			return set()
		visited.add(page_url)
		resp = client.get(page_url, headers={"user-agent": USER_AGENT}, timeout=20)
		resp.raise_for_status()
		html = resp.text
		ids = set(re.findall(r'class="link" href="/ebooks/(\d+)"', html)) | set(
			re.findall(r'itemprop="[^"]*"[^>]*href="/ebooks/(\d+)"', html)
		)
		nxt = re.search(r'href="(/ebooks/(?:bookshelf|subject)/[^?"]*\?[^"]*start_index=\d+)"', html)
		if nxt:
			ids |= recurse("https://www.gutenberg.org" + nxt.group(1))
		return ids

	return recurse(url)


def _truncate_teaser(text: str, cap: int = 150) -> str:
	"""Python mirror of truncateTeaser() in web/src/lib/server/resource-schema.ts —
	keep the two in sync. Cut at the last sentence end within the cap, else the
	last whole word."""
	if len(text) <= cap:
		return text
	cut = text[:cap]
	sentence_end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
	if sentence_end >= cap // 2:
		return cut[: sentence_end + 1]
	space = cut.rfind(" ")
	if space > cap // 2:
		return cut[:space] + "…"
	return cut[:-1] + "…"


def _normalize_texts(record: dict) -> None:
	"""Mirror the insert endpoint's rule: description ≤ 150 (card teaser);
	fallback text over the cap promotes to summary when it meets the 250-char
	minimum. Direct inserts (pymongo) bypass the API's normalize step — the DB
	validator doesn't exist on Atlas — so this must run here too."""
	from app.ai import MAX_DESCRIPTION_CHARS, MIN_SUMMARY_CHARS

	description = record.get("description") or ""
	summary = record.get("summary")
	if len(description) > MAX_DESCRIPTION_CHARS:
		if summary is None and len(description) >= MIN_SUMMARY_CHARS:
			summary = description  # the full fallback text stays searchable
		description = _truncate_teaser(description, MAX_DESCRIPTION_CHARS)
	elif summary is not None and len(summary) < MIN_SUMMARY_CHARS:
		summary = None
	record["description"], record["summary"] = description, summary


def _skippable_title(title: str | None) -> bool:
	return title and any(p.search(title) for p in SKIP_TITLE_PATTERNS)


async def _process_one(
	id: str,
	slots: asyncio.Semaphore,
	collection,  # motor collection
	results: dict,
) -> None:
	# Imported here so setup (env override in main) lands first.
	from app.book import _gutendex, _record_from_book, _scrape_page

	async with slots:
		try:
			# Same two-source lookup + AI cleanup as POST /api/book-metadata.
			book = await _gutendex(id) or await _scrape_page(id)
			if book is None:
				results["failed"].append((id, "not found"))
				print(f"  {id}: not found in catalog or website, skipping")
				return
			record = await _record_from_book(id, book)
			if _skippable_title(record.get("title")):
				print(f"  {id}: catalog artifact ({record['title'][:40]}), skipping")
				results["failed"].append((id, "catalog artifact"))
				return
			if not record.get("link"):
				results["failed"].append((id, "no text link (audio-only?)"))
				print(f"  {id}: no downloadable text link (audio-only?), skipping")
				return
			# details/raw are UI-only and the DB validator rejects unknown keys.
			record.pop("details", None)
			record.pop("raw", None)
			_normalize_texts(record)
			await collection.insert_one(
				{**record, "status": record["status"] or "approved", "createdAt": datetime.now(UTC)}
			)
			results["inserted"] += 1
			title = re.sub(r"\s+", " ", record["title"] or "?")[:56]
			print(
				f"  {id}: ✅ {title} | desc {len(record['description'] or '')} chars"
				f" | summary {len(record['summary'] or '')} | cover {'yes' if record['imgurl'] else 'no'}"
			)
		except Exception as exc:  # noqa: BLE001 — one bad book must not stop the batch
			results["failed"].append((id, str(exc)[:80]))
			print(f"  {id}: ❌ {type(exc).__name__}: {exc}")


async def main(db_target: str, reseed: bool = False) -> None:
	# Real env vars override the root .env — make --db local mean it
	if db_target == "local":
		import os

		os.environ["ATLAS_URI"] = ""

	from app.book import GUTENBERG_ID
	from app.config import resolve_db_config
	from app.db import db as motor_db

	ids: set[str] = set()
	with httpx.Client(follow_redirects=True) as walker:
		for list_url in LIST_URLS:
			collected = walk_listing(walker, list_url)
			print(f"listing {list_url.rsplit('/', 1)[-1]}: {len(collected)} ids")
			ids |= collected

	_, db_name, target = resolve_db_config()
	collection = motor_db["resources"]
	if reseed:
		result = await collection.delete_many({"resourceformat": "book"})
		print(f"reseed: removed {result.deleted_count} existing book records")

	# Duplicates: any stored record pointing at the same Gutenberg id. The two
	# conditions are separate $or elements — one element holding both keys
	# would require BOTH fields to match (sitelink is null on book records).
	existing: set[str] = set()
	async for doc in collection.find(
		{"$or": [{"link": {"$regex": "/ebooks/"}}, {"sitelink": {"$regex": "/ebooks/"}}]},
		{"link": 1, "sitelink": 1},
	):
		for field in (doc.get("sitelink") or "", doc.get("link") or ""):
			if m := GUTENBERG_ID.search(field):
				existing.add(m.group(1))
	print(f"target: {target} ({db_name}) | ids: {len(ids)} | already stored: {len(existing)}")

	# Repair pass, idempotent every run:
	# (1) books inserted pointing at the raw .txt file → link the readable
	#     page instead (sitelink drops — implicit for Gutenberg books);
	# (2) descriptions cut mid-sentence by the old hard slice → re-cut at a
	#     sentence boundary and keep the full text searchable as `summary`.
	from app.ai import MAX_DESCRIPTION_CHARS, MIN_SUMMARY_CHARS
	from app.book import _clean_title

	repaired = 0
	async for doc in collection.find(
		{"resourceformat": "book"}, {"link": 1, "sitelink": 1, "description": 1, "summary": 1, "title": 1}
	):
		updates: dict = {}
		link = doc.get("link") or ""
		sitelink = doc.get("sitelink") or None
		m = GUTENBERG_ID.search(link) or (sitelink and GUTENBERG_ID.search(sitelink))
		if ".txt" in link and m:
			updates["link"] = f"https://www.gutenberg.org/ebooks/{m.group(1)}"
			updates["sitelink"] = None
		if (title := doc.get("title")) and (cleaned := _clean_title(title)) != title:
			updates["title"] = cleaned
		description = doc.get("description") or ""
		summary = doc.get("summary")
		if len(description) > MAX_DESCRIPTION_CHARS:
			if summary is None and len(description) >= MIN_SUMMARY_CHARS:
				summary = description
			updates["description"] = _truncate_teaser(description, MAX_DESCRIPTION_CHARS)
			updates["summary"] = summary
		if updates:
			await collection.update_one({"_id": doc["_id"]}, {"$set": updates})
			repaired += 1
	print(f"books repaired: {repaired}")

	# Catalog artifacts are not resources — drop any that slipped in.
	removed = 0
	# (3) summaries grounded in packaging instead of content (performance
	#     copyrights, e-text credits) are worse than none: null them.
	junk_summary = {
		"resourceformat": "book",
		"summary": {"$regex": "Performance copyright|E-text prepared|Distributed Proofreading|Project Gutenberg Public Domain", "$options": "i"},
	}
	junk_count = await collection.count_documents(junk_summary)
	if junk_count:
		await collection.update_many(junk_summary, {"$set": {"summary": None}})
		print(f"junk summaries nulled: {junk_count}")
	else:
		print("junk summaries: none")

	for pattern in SKIP_TITLE_PATTERNS:
		result = await collection.delete_many({"resourceformat": "book", "title": pattern})
		removed += result.deleted_count
	if removed:
		print(f"catalog artifacts removed: {removed}")

	if args.enrich or args.refresh:
		# --refresh re-cleans every book with the current prompt (titles are
		# catalog titles today); --enrich only fills missing description/summary.
		await _enrich(collection, refresh=args.refresh)
		return

	results: dict = {"inserted": 0, "failed": []}
	slots = asyncio.Semaphore(AI_CONCURRENCY)
	todo = sorted((id for id in ids if id not in existing), key=int)
	await asyncio.gather(*(_process_one(id, slots, collection, results) for id in todo))

	print(json.dumps({"inserted": results["inserted"], "duplicates skipped": len(existing), "failed": results["failed"]}, indent=1))

	await _dedupe_titles(collection)


async def _dedupe_titles(collection) -> None:
	"""One card per work: identical titles across Gutenberg ids are editions of
	the same book (e.g. The Souls of Black Folk = ids 408 and 28844). Keep the
	record with the longest summary — ties keep the lowest book id."""
	from app.db import db as _db  # noqa — collection param is motor; group via find

	groups: dict[str, list] = {}
	async for doc in collection.find({"resourceformat": "book"}, {"title": 1, "summary": 1, "sitelink": 1}):
		title = (doc.get("title") or "").strip()
		if title:
			groups.setdefault(title, []).append(doc)

	removed = 0
	for docs in groups.values():
		if len(docs) < 2:
			continue
		keep = min(
			docs,
			key=lambda d: (
				-len(d.get("summary") or ""),
				len(f"{(d.get('sitelink') or '')}"),
			),
		)
		for doc in docs:
			if doc["_id"] != keep["_id"]:
				await collection.delete_one({"_id": doc["_id"]})
				removed += 1
				print(f"  title-dedupe: removed '{(doc.get('title') or '')[:52]}' ({doc['_id']}) — kept {keep['_id']}")
	print(f"title dedupe removed: {removed}")


async def _enrich(collection, refresh: bool = False) -> None:
	"""Re-run the catalog + AI cleanup for books that came in during gutendex
	outages (no description and/or no summary). --refresh re-cleans ALL books
	(prompt changes, e.g. shorter titles). Only non-null cleaned fields are
	written, so a still-broken source updates nothing."""
	from app.book import GUTENBERG_ID, _gutendex, _record_from_book, _scrape_page

	query = (
		{"resourceformat": "book"}
		if refresh
		else {
			"resourceformat": "book",
			"$or": [
				{"summary": None},
				{"description": {"$in": [None, ""]}},
				{"attribution": {"$in": [None, ""]}},  # authorless: maybe the catalog has it now
			],
		}
	)
	todo: set[str] = set()
	async for doc in collection.find(
		query,
		# Projection must include BOTH link fields: the link-swap repair nulls
		# `sitelink`, and the id extraction falls back to `link`.
		{"link": 1, "sitelink": 1},
	):
		if m := GUTENBERG_ID.search(doc.get("sitelink") or doc.get("link") or ""):
			todo.add(m.group(1))
	print(f"enrichment candidates: {len(todo)}")

	results: dict = {"updated": 0, "failed": []}
	slots = asyncio.Semaphore(AI_CONCURRENCY)

	async def one(id: str) -> None:
		async with slots:
			try:
				book = await _gutendex(id) or await _scrape_page(id)
				if book is None:
					return  # gutendex still down / bad id — try again later
				record = await _record_from_book(id, book)
				if _skippable_title(record.get("title")):
					await collection.delete_one({"resourceformat": "book", "title": record["title"]})
					print(f"  {id}: catalog artifact — removed")
					return
				_normalize_texts(record)
				updates = {
					k: v
					for k, v in record.items()
					if k in ("title", "description", "summary", "attribution", "contentcategory", "imgurl")
					and v not in (None, "")
				}
				if updates:
					# boundary-safe: /ebooks/<id> must end there (links end with
					# the id, with .txt on legacy records, or with a query).
					boundary = rf"/ebooks/{id}(\.|\\?|$)"
					await collection.update_one(
						{"$or": [{"link": {"$regex": boundary}}, {"sitelink": {"$regex": boundary}}]},
						{"$set": updates},
					)
					results["updated"] += 1
					print(f"  {id}: enriched ↑")
			except Exception as exc:  # noqa: BLE001
				results["failed"].append((id, str(exc)[:80]))

	await asyncio.gather(*(one(id) for id in sorted(todo, key=int)))
	print(json.dumps(results, indent=1))


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--db", choices=["local", "atlas"], default="local")
	parser.add_argument(
		"--enrich", action="store_true", help="re-clean books missing description/summary (needs gutendex healthy)"
	)
	parser.add_argument(
		"--refresh", action="store_true", help="re-clean ALL books with the current prompt (titles, descriptions)"
	)
	parser.add_argument(
		"--reseed", action="store_true", help="replace all book records with a fresh listing import"
	)
	args = parser.parse_args()
	if args.reseed and (args.enrich or args.refresh):
		parser.error("--reseed cannot be combined with --enrich or --refresh")
	asyncio.run(main(args.db, reseed=args.reseed))
