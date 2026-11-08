import asyncio

import pytest
from fastapi import HTTPException

from app.video import _record_from_video, _transcript_excerpts, _video_id


def test_video_id_accepts_common_youtube_urls():
	urls = [
		"https://www.youtube.com/watch?v=D9Ihs241zeg",
		"https://youtu.be/D9Ihs241zeg?t=10",
		"https://www.youtube.com/shorts/D9Ihs241zeg",
		"https://www.youtube.com/live/D9Ihs241zeg",
		"https://www.youtube.com/embed/D9Ihs241zeg",
	]
	assert [_video_id(url) for url in urls] == ["D9Ihs241zeg"] * len(urls)


def test_video_id_rejects_non_video_urls():
	with pytest.raises(HTTPException):
		_video_id("https://example.com/watch?v=D9Ihs241zeg")
	with pytest.raises(HTTPException):
		_video_id("https://www.youtube.com/feed/history")


def test_transcript_excerpts_cover_long_videos():
	text = ("beginning " * 5000) + ("middle " * 5000) + ("end " * 5000)
	excerpts = _transcript_excerpts(text)
	assert excerpts.startswith("Beginning:\nbeginning")
	assert "Middle:\n" in excerpts
	assert "End:\n" in excerpts
	assert len(excerpts) < 46_000


def test_video_record_uses_transcript_in_shared_cleanup(monkeypatch):
	seen = {}

	async def fake_clean(fields):
		seen.update(fields)
		return {
			"title": "Cleaned Video",
			"description": "A grounded teaser.",
			"summary": "A grounded summary. " * 20,
			"attribution": "A Channel",
			"contentcategory": "history",
		}

	monkeypatch.setattr("app.video.clean_record", fake_clean)
	record = asyncio.run(
		_record_from_video(
			"D9Ihs241zeg",
			{"title": "Video", "author_name": "A Channel", "thumbnail_url": "https://img.youtube.com/cover.jpg"},
			{"text": "The speaker discusses Black history.", "language": "en"},
		)
	)
	assert "The speaker discusses Black history." in seen["text"]
	assert record["link"] == "https://www.youtube.com/watch?v=D9Ihs241zeg"
	assert record["resourceformat"] == "video"
	assert record["imgurl"] == "https://img.youtube.com/cover.jpg"
	assert record["summary"].startswith("A grounded summary.")
