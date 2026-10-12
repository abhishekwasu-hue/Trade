from __future__ import annotations

import uuid

import httpx
import pytest

from tests.conftest import make_token


async def test_me_requires_bearer_token(client: httpx.AsyncClient) -> None:
    resp = await client.get("/v1/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize(
    "token",
    [
        make_token(uuid.uuid4(), secret="wrong-secret-wrong-secret-wrong-secret-xx"),
        make_token(uuid.uuid4(), aud="anon"),
        make_token(uuid.uuid4(), exp_offset=-10),
        make_token("not-a-uuid"),
        "garbage",
    ],
    ids=["bad-signature", "bad-audience", "expired", "bad-subject", "malformed"],
)
async def test_rejects_invalid_tokens(client: httpx.AsyncClient, token: str) -> None:
    resp = await client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_me_returns_404_before_profile_exists(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.get("/v1/me", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "profile_not_found"
