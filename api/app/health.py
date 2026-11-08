import asyncio
import logging
import time

import httpx
import psutil
from fastapi import APIRouter, Response, status

from app.config import settings
from app.db import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])
START_TIME = time.monotonic()
DATABASE_CHECK_TIMEOUT_SECONDS = 3
AI_CHECK_TIMEOUT_SECONDS = 10
AI_CHECK_CACHE_SECONDS = 300
_gemini_check_cache: tuple[float, str] | None = None
_gemini_check_lock = asyncio.Lock()


async def check_mongodb() -> str:
	"""Check the database required for the API to serve requests."""
	try:
		await asyncio.wait_for(
			db.command("ping"),
			timeout=DATABASE_CHECK_TIMEOUT_SECONDS,
		)
	except Exception:
		logger.warning("MongoDB health check failed", exc_info=True)
		return "unreachable"
	return "healthy"


async def probe_api_gemini() -> str:
	"""Verify the API's configured Gemini model can generate a small response."""
	if not settings.gemini_api_key:
		return "not_configured"

	url = (
		"https://generativelanguage.googleapis.com/v1beta/models/"
		f"{settings.gemini_model}:generateContent"
	)
	payload = {
		"contents": [{"role": "user", "parts": [{"text": "Reply with OK."}]}],
		"generationConfig": {"maxOutputTokens": 4, "temperature": 0},
	}
	try:
		async with httpx.AsyncClient(timeout=AI_CHECK_TIMEOUT_SECONDS) as client:
			result = await client.post(
				url,
				json=payload,
				headers={"x-goog-api-key": settings.gemini_api_key},
			)
		result.raise_for_status()
		candidates = result.json().get("candidates", [])
		parts = candidates[0]["content"]["parts"]
		if not any(isinstance(part.get("text"), str) and part["text"].strip() for part in parts):
			raise ValueError("Gemini returned no generated text")
	except Exception:
		logger.warning("API Gemini health check failed", exc_info=True)
		return "unhealthy"
	return "healthy"


async def check_api_gemini() -> str:
	"""Cache the billable generation probe so dashboard polling does not call it repeatedly."""
	global _gemini_check_cache
	if not settings.gemini_api_key:
		return "not_configured"

	now = time.monotonic()
	if _gemini_check_cache and now - _gemini_check_cache[0] < AI_CHECK_CACHE_SECONDS:
		return _gemini_check_cache[1]

	async with _gemini_check_lock:
		now = time.monotonic()
		if _gemini_check_cache and now - _gemini_check_cache[0] < AI_CHECK_CACHE_SECONDS:
			return _gemini_check_cache[1]
		result = await probe_api_gemini()
		_gemini_check_cache = (time.monotonic(), result)
		return result


@router.get("")
async def get_detailed_health(response: Response) -> dict:
	"""Return database and AI readiness, process uptime, and host resource usage."""
	memory = psutil.virtual_memory()
	database_status, gemini_status = await asyncio.gather(check_mongodb(), check_api_gemini())
	checks = {"database": database_status, "api_gemini": gemini_status}
	is_healthy = database_status == "healthy" and gemini_status in {"healthy", "not_configured"}

	if not is_healthy:
		response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

	return {
		"status": "healthy" if is_healthy else "unhealthy",
		"timestamp": time.time(),
		"uptime_seconds": int(time.monotonic() - START_TIME),
		"metrics": {
			"cpu_usage_percent": psutil.cpu_percent(interval=None),
			"memory_usage_percent": memory.percent,
			"memory_available_gb": round(memory.available / (1024**3), 2),
		},
		"checks": checks,
	}
