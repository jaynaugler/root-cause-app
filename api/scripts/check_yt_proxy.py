"""Diagnose the YouTube transcript proxy chain used by app/video.py.

Reads YT_PROXY_USERNAME / YT_PROXY_PASSWORD from the environment (falling back
to the repo-root .env), then answers three questions in order, because they
have different fixes:

1. are the Webshare proxy credentials configured at all?
2. can p.webshare.io be reached with them, and what kind of IP exits? Webshare's
   free plan hands out datacenter IPs — YouTube blocks those like Render's, so
   only a residential exit IP can work.
3. does a real YouTube transcript fetch succeed through that proxy? The
   exception type matters: IpBlocked / RequestBlocked = the exit IP was
   rejected (wrong plan or dead proxy); PoTokenRequired = the chain works but
   YouTube wants a PO token for that request.

Usage (from api/):
  uv run python scripts/check_yt_proxy.py                 # a known-captioned video
  uv run python scripts/check_yt_proxy.py dQw4w9WgXcQ     # any video id or URL
"""

import os
import sys
from pathlib import Path
from urllib.parse import quote

ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"

# Known video with human-written captions, used when no id is passed.
DEFAULT_VIDEO_ID = "dQw4w9WgXcQ"


def _env(name: str) -> str | None:
	if value := os.environ.get(name):
		return value.strip() or None
	if not ROOT_ENV.exists():
		return None
	for line in ROOT_ENV.read_text().splitlines():
		line = line.strip()
		# Split on the first '=' only — proxy passwords are allowed to contain
		# '#', '@' etc., so this parser must not try to strip comments or be
		# clever about characters inside the value.
		if line.startswith(f"{name}=") and "=" in line:
			return line.split("=", 1)[1].strip().strip("\"'").strip() or None
	return None


def main() -> int:
	import httpx
	from youtube_transcript_api import (
		IpBlocked,
		PoTokenRequired,
		RequestBlocked,
		YouTubeRequestFailed,
		YouTubeTranscriptApi,
		YouTubeTranscriptApiException,
	)
	from youtube_transcript_api.proxies import WebshareProxyConfig

	username, password = _env("YT_PROXY_USERNAME"), _env("YT_PROXY_PASSWORD")
	if not (username and password):
		print("1. ✗ YT_PROXY_USERNAME / YT_PROXY_PASSWORD not set (env or repo-root .env)")
		print("   → On Render this means video.py is using the server IP directly.")
		return 1
	print(f"1. ✓ credentials found (username {username[:3]}…, {len(password)}-char password)")

	proxy_url = (
		f"http://{quote(username, safe='')}-rotate:{quote(password, safe='')}"
		f"@p.webshare.io:80/"
	)
	try:
		with httpx.Client(proxy=proxy_url, timeout=20) as client:
			info = client.get("https://ipinfo.io/json").json()
	except httpx.ProxyError as exc:
		print(f"2. ✗ proxy rejected our credentials/auth: {exc}")
		print("   → check the username/password in the Webshare dashboard")
		return 2
	except Exception as exc:  # noqa: BLE001 — a diagnostic reports everything
		print(f"2. ✗ p.webshare.io unreachable through the proxy: {type(exc).__name__}: {exc}")
		return 2
	org = info.get("org", "unknown org")
	print(f"2. ✓ proxy reachable — exit IP {info.get('ip')} ({info.get('country')}, {org})")
	if not re.search(r"(?i)mobile|residential|comcast|verizon|at&t|spectrum|rogers", org):
		print("   ⚠ exit IP looks like a datacenter/managed host — the Webshare plan on")
		print("     this account may not be residential. YouTube will keep blocking it.")

	video_id = (
		re.search(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})", sys.argv[1]).group(1)
		if len(sys.argv) > 1
		else DEFAULT_VIDEO_ID
	)
	api = YouTubeTranscriptApi(WebshareProxyConfig(username, password))
	print(f"3. fetching a transcript for {video_id} through the proxy…")
	try:
		transcripts = list(api.list(video_id))
		first = transcripts[0] if transcripts else None
		if first is None:
			print("   ✗ YouTube served an empty transcript list (no captions on this video?)")
			return 3
		text = first.fetch().to_raw_data()[0]["text"]
		print(f"✓ full chain works — {len(transcripts)} transcript(s), first line: {text[:60]!r}")
		return 0
	except (IpBlocked, RequestBlocked, YouTubeRequestFailed) as exc:
		print(f"3. ✗ YouTube rejected the proxy's exit IP — {type(exc).__name__}: {exc}")
		print("   → the Webshare plan's IPs are not residential/trusted enough;")
		print("     upgrade to their Residential plan (or try another provider)")
		return 3
	except PoTokenRequired as exc:
		print(f"3. ✗ chain works but YouTube demands a PO token — {type(exc).__name__}: {exc}")
		print("   → not a proxy problem; fetching transcripts for this video would need")
		print("     a PO-token provider wired into youtube-transcript-api")
		return 3
	except YouTubeTranscriptApiException as exc:
		print(f"3. ✗ {type(exc).__name__}: {exc}")
		return 3


if __name__ == "__main__":
	raise SystemExit(main())
