import asyncio

from app.ai import _description
from app.book import _clean_book_text, _record_from_book, _text_excerpts


def test_clean_book_text_removes_gutenberg_packaging():
	body = "license\n*** START OF THE PROJECT GUTENBERG EBOOK TEST ***\nActual\nbook text.\n*** END OF THE PROJECT GUTENBERG EBOOK TEST ***\nlicense"
	assert _clean_book_text(body) == "Actual book text."


def test_text_excerpts_cover_long_books_without_truncating_short_ones():
	short = "A complete short book."
	assert _text_excerpts(short) == short

	long = ("beginning " * 5000) + ("middle " * 5000) + ("end " * 5000)
	excerpts = _text_excerpts(long)
	assert excerpts.startswith("Beginning:\nbeginning")
	assert "Middle:\n" in excerpts
	assert "End:\n" in excerpts
	assert len(excerpts) < 46_000


def test_description_cap_never_exceeds_limit_or_cuts_a_word():
	assert _description("word " * 40).endswith("…")
	assert len(_description("word " * 40)) <= 150
	assert len(_description("x" * 200)) == 150


def test_book_cleanup_uses_plain_text_even_with_catalog_summary(monkeypatch):
	seen = {}

	async def fake_text(candidates):
		return "The book body discusses emancipation and education."

	async def fake_clean(fields):
		seen.update(fields)
		return {
			"title": "Test Book",
			"description": "A grounded teaser.",
			"summary": "A grounded summary. " * 20,
			"attribution": "An Author",
			"contentcategory": "history",
		}

	monkeypatch.setattr("app.book._book_text", fake_text)
	monkeypatch.setattr("app.book.clean_record", fake_clean)
	book = {
		"title": "Test Book",
		"authors": [{"name": "An Author"}],
		"summaries": ["A catalog summary."],
		"subjects": [],
		"formats": {"text/plain": "https://www.gutenberg.org/cache/epub/1/pg1.txt"},
	}
	record = asyncio.run(_record_from_book("1", book))
	assert "The book body discusses emancipation and education." in seen["text"]
	assert "A catalog summary." in seen["text"]
	assert record["summary"].startswith("A grounded summary.")


def test_failed_cleanup_does_not_save_book_excerpts_as_summary(monkeypatch):
	async def fake_text(candidates):
		return "Contents and front matter from the book."

	async def fail_clean(fields):
		raise RuntimeError("AI unavailable")

	monkeypatch.setattr("app.book._book_text", fake_text)
	monkeypatch.setattr("app.book.clean_record", fail_clean)
	record = asyncio.run(_record_from_book("1", {"title": "Test Book", "authors": []}))
	assert record["description"] is None
	assert record["summary"] is None
