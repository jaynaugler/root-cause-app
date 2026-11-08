import asyncio
import json

import httpx
from fastapi import Response, status

from app.health import get_detailed_health, probe_api_gemini


def test_gemini_probe_checks_generation_without_leaking_key(monkeypatch):
	monkeypatch.setattr("app.health.settings.gemini_api_key", "test-key")
	requests = []
	async_client = httpx.AsyncClient

	async def handle_request(request):
		requests.append(request)
		return httpx.Response(
			200,
			json={"candidates": [{"content": {"parts": [{"text": "OK"}]}}]},
		)

	def client_factory(**kwargs):
		return async_client(transport=httpx.MockTransport(handle_request), **kwargs)

	monkeypatch.setattr("app.health.httpx.AsyncClient", client_factory)

	result = asyncio.run(probe_api_gemini())

	assert result == "healthy"
	assert len(requests) == 1
	assert requests[0].headers["x-goog-api-key"] == "test-key"
	assert json.loads(requests[0].content)["generationConfig"]["maxOutputTokens"] == 4


def test_gemini_probe_skips_when_not_configured(monkeypatch):
	monkeypatch.setattr("app.health.settings.gemini_api_key", "")
	assert asyncio.run(probe_api_gemini()) == "not_configured"


def test_health_reports_healthy_database(monkeypatch):
	monkeypatch.setattr("app.health.settings.gemini_api_key", "")

	async def ping(*_args, **_kwargs):
		return {"ok": 1}

	monkeypatch.setattr("app.health.db.command", ping)

	response = Response()
	payload = asyncio.run(get_detailed_health(response))

	assert response.status_code == status.HTTP_200_OK
	assert payload["status"] == "healthy"
	assert payload["checks"] == {"database": "healthy", "api_gemini": "not_configured"}
	assert payload["uptime_seconds"] >= 0
	assert 0 <= payload["metrics"]["memory_usage_percent"] <= 100


def test_health_returns_service_unavailable_when_database_fails(monkeypatch):
	monkeypatch.setattr("app.health.settings.gemini_api_key", "")

	async def ping(*_args, **_kwargs):
		raise RuntimeError("database unavailable")

	monkeypatch.setattr("app.health.db.command", ping)

	response = Response()
	payload = asyncio.run(get_detailed_health(response))

	assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
	assert payload["status"] == "unhealthy"
	assert payload["checks"] == {"database": "unreachable", "api_gemini": "not_configured"}
