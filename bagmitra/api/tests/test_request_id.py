from __future__ import annotations

import httpx


async def test_generates_request_id_when_absent(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health/live")
    rid = resp.headers["X-Request-ID"]
    assert len(rid) == 32


async def test_echoes_valid_incoming_request_id(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health/live", headers={"X-Request-ID": "abc-123"})
    assert resp.headers["X-Request-ID"] == "abc-123"


async def test_replaces_malicious_request_id(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health/live", headers={"X-Request-ID": "bad id\nInjected: 1"})
    assert resp.headers["X-Request-ID"] != "bad id\nInjected: 1"
    assert len(resp.headers["X-Request-ID"]) == 32


async def test_error_envelope_contains_request_id(client: httpx.AsyncClient) -> None:
    resp = await client.get("/does-not-exist", headers={"X-Request-ID": "rid-1"})
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["request_id"] == "rid-1"
