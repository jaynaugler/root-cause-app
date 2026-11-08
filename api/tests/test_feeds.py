import asyncio

from app.feeds import _plain_text, _record_from_entry


def test_plain_text_removes_feed_html():
	assert _plain_text("<p>A <strong>Black</strong> history &amp; culture story</p>") == "A Black history & culture story"


def test_article_entry_uses_shared_cleanup(monkeypatch):
	seen = {}

	async def fake_clean(fields):
		seen.update(fields)
		return {"description": "Generated teaser", "summary": "S" * 250}

	monkeypatch.setattr("app.feeds.clean_record", fake_clean)
	entry = {
		"title": "A News Story",
		"link": "https://example.com/story",
		"summary": "<p>A grounded news summary.</p>",
		"author": "A Publisher",
	}
	record = asyncio.run(_record_from_entry(entry, {"title": "News Feed"}))
	assert seen["text"] == "A grounded news summary."
	assert record["link"] == "https://example.com/story"
	assert record["sitelink"] is None
	assert record["resourceformat"] == "article"
	assert record["status"] == "pending"
	assert record["summary"] == "S" * 250


def test_podcast_entry_uses_audio_link_and_episode_page(monkeypatch):
	async def fake_clean(fields):
		return {}

	monkeypatch.setattr("app.feeds.clean_record", fake_clean)
	entry = {
		"title": "An Episode",
		"link": "https://example.com/episode",
		"itunes_summary": "An episode synopsis.",
		"enclosures": [{"type": "audio/mpeg", "href": "https://example.com/episode.mp3"}],
		"itunes_image": {"href": "https://example.com/cover.jpg"},
	}
	record = asyncio.run(_record_from_entry(entry, {}))
	assert record["link"] == "https://example.com/episode.mp3"
	assert record["sitelink"] == "https://example.com/episode"
	assert record["resourceformat"] == "podcast"
	assert record["imgurl"] == "https://example.com/cover.jpg"
