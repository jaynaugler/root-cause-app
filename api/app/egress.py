"""Outbound page and file GETs through ZenRows when configured.

Render hosts this API on a datacenter IP, and the sites it scrapes (podcast and
archive feeds, Gutenberg pages, arbitrary PDF hosts, recorded resource links)
block or bot-challenge traffic from server IPs. When ZENROWS_API_KEY is set,
https://api.zenrows.com/v1/ relays the request: mode=auto escalates to
JavaScript rendering or premium proxies only when the target requires it, and
is billed for the configuration that succeeded.

YouTube transcripts do not go through here — youtube_transcript_api drives
YouTube's own API (and wants a real HTTP proxy), so app/video.py keeps its
Webshare proxy setup instead.

No key configured (typical for local dev) means egress_get() and zenrows_get()
fetch directly as before, which is also why the key should stay out of the
repo-root .env: unset locally, credits are only spent by Render.
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger("uvicorn.error")

ZENROWS_ENDPOINT = "https://api.zenrows.com/v1/"


def zenrows_enabled() -> bool:
	"""True when GETs should relay through ZenRows (key set in the environment)."""
	return bool(settings.zenrows_api_key.strip())


async def zenrows_get(
	client: httpx.AsyncClient,
	url: str,
	*,
	headers: httpx.Headers | dict | None = None,
	timeout: float | None = None,
) -> httpx.Response | None:
	"""One GET relayed through ZenRows.

	Returns None when no key is configured, so callers can run their direct
	path. The relayed response is returned as-is: a non-200 status is a relay
	or fetch failure (ZenRows maps target problems to its own codes — see
	https://docs.zenrows.com/api-error-codes), and callers degrade to direct.
	"""
	if not zenrows_enabled():
		return None
	kwargs: dict = {
		"params": {
			"apikey": settings.zenrows_api_key.strip(),
			"url": str(url),
			"mode": "auto",
		}
	}
	if headers is not None:
		kwargs["headers"] = headers
	if timeout is not None:
		kwargs["timeout"] = timeout
	return await client.get(ZENROWS_ENDPOINT, **kwargs)


async def egress_get(
	client: httpx.AsyncClient,
	url: str,
	*,
	headers: httpx.Headers | dict | None = None,
	timeout: float | None = None,
) -> httpx.Response:
	"""Drop-in GET that relays through ZenRows when configured.

	ZenRows refusals (restricted domains such as government sites, spent
	credits, unreachable relay) fall back to the same request made directly, so
	a relayed fetch can only fail the way the direct request could before. The
	fallback buffers the whole body — only use this when the body is bounded.
	"""
	try:
		relay = await zenrows_get(client, url, headers=headers, timeout=timeout)
	except (httpx.TimeoutException, httpx.HTTPError) as exc:
		logger.warning("ZenRows relay unreachable for %s (%s) — fetching directly", url, exc)
		return await client.get(url, headers=headers, timeout=timeout)
	if relay is None:
		return await client.get(url, headers=headers, timeout=timeout)
	if relay.status_code == 200:
		return relay
	detail = ""
	try:
		detail = relay.json().get("code", "")
	except ValueError:
		pass
	logger.warning("ZenRows refused %s (HTTP %d %s) — fetching directly", url, relay.status_code, detail)
	return await client.get(url, headers=headers, timeout=timeout)
