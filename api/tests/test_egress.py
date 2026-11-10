"""The ZenRows egress relay in app/egress.py: relays only with a key configured,
and every refusal falls back to the same request made directly."""

import asyncio

import httpx
import pytest

from app.egress import egress_get


class FakeClient:
	"""httpx.AsyncClient stand-in: records each get() and replays responses."""

	def __init__(self, *responses):
		self.responses = list(responses)
		self.calls: list[tuple[str, dict]] = []

	async def get(self, url, **kwargs):
		self.calls.append((url, kwargs))
		outcome = self.responses.pop(0)
		if isinstance(outcome, Exception):
			raise outcome
		return outcome


def target_response(status: int = 200, text: str = "hi") -> httpx.Response:
	return httpx.Response(status, text=text, request=httpx.Request("GET", "https://target.example/page"))


def relay_response(status: int = 200, body: str = "page html") -> httpx.Response:
	return httpx.Response(status, text=body, request=httpx.Request("GET", "https://api.zenrows.com/v1/"))


def relay_error(status: int, code: str) -> httpx.Response:
	return httpx.Response(
		status, json={"code": code}, request=httpx.Request("GET", "https://api.zenrows.com/v1/")
	)


def run(coro):
	return asyncio.run(coro)


def test_without_key_fetches_directly(monkeypatch):
	monkeypatch.setattr("app.config.settings.zenrows_api_key", "")
	client = FakeClient(target_response())
	resp = run(egress_get(client, "https://target.example/page", headers={"user-agent": "ua"}))

	assert resp.status_code == 200
	assert len(client.calls) == 1
	assert client.calls[0][0] == "https://target.example/page"


def test_with_key_returns_relayed_response(monkeypatch):
	monkeypatch.setattr("app.config.settings.zenrows_api_key", "k-test")
	client = FakeClient(relay_response(body="relayed html"))
	resp = run(egress_get(client, "https://target.example/page"))

	assert resp.status_code == 200
	assert resp.text == "relayed html"
	# One call only, at the ZenRows endpoint with the key and mode=auto.
	assert len(client.calls) == 1
	url, kwargs = client.calls[0]
	assert url == "https://api.zenrows.com/v1/"
	assert kwargs["params"]["apikey"] == "k-test"
	assert kwargs["params"]["mode"] == "auto"
	assert kwargs["params"]["url"] == "https://target.example/page"


@pytest.mark.parametrize(
	("status", "code"),
	[(400, "REQS001"), (402, "AUTH004"), (422, "RESP001"), (429, "AUTH008")],
)
def test_zenrows_refusal_falls_back_to_direct(monkeypatch, status, code):
	monkeypatch.setattr("app.config.settings.zenrows_api_key", "k-test")
	client = FakeClient(relay_error(status, code), target_response())
	resp = run(egress_get(client, "https://target.example/page"))

	assert resp.status_code == 200
	assert [c[0] for c in client.calls] == [
		"https://api.zenrows.com/v1/",
		"https://target.example/page",
	]


def test_unreachable_relay_falls_back_to_direct(monkeypatch):
	monkeypatch.setattr("app.config.settings.zenrows_api_key", "k-test")
	client = FakeClient(httpx.ConnectError("no route"), target_response())
	resp = run(egress_get(client, "https://target.example/page"))

	assert resp.status_code == 200
	assert len(client.calls) == 2


def test_double_failure_surfaces_the_error(monkeypatch):
	monkeypatch.setattr("app.config.settings.zenrows_api_key", "k-test")
	client = FakeClient(relay_error(422, "RESP001"), target_response(404))

	resp = run(egress_get(client, "https://target.example/page"))
	assert resp.status_code == 404
