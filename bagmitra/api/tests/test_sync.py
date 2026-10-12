from __future__ import annotations

import uuid
from typing import Any

import httpx

from tests.conftest import make_token


def profile_mutation(
    user_id: uuid.UUID,
    *,
    mutation_id: uuid.UUID | None = None,
    updated_at: str = "2026-10-01T06:00:00+05:30",
    **fields: Any,
) -> dict[str, Any]:
    payload = {"display_name": "Abhishek", "language": "mr", "district": "Nagpur"}
    payload.update(fields)
    return {
        "client_mutation_id": str(mutation_id or uuid.uuid4()),
        "entity": "farmer_profile",
        "entity_id": str(user_id),
        "op": "upsert",
        "client_updated_at": updated_at,
        "payload": payload,
    }


async def push(
    client: httpx.AsyncClient, headers: dict[str, str], *mutations: dict[str, Any]
) -> list[dict[str, Any]]:
    resp = await client.post("/v1/sync/push", json={"mutations": list(mutations)}, headers=headers)
    assert resp.status_code == 200, resp.text
    results: list[dict[str, Any]] = resp.json()["results"]
    return results


async def test_push_applies_profile_and_me_returns_it(
    client: httpx.AsyncClient, auth_headers: dict[str, str], user_id: uuid.UUID
) -> None:
    [result] = await push(client, auth_headers, profile_mutation(user_id))
    assert result["status"] == "applied"

    me = await client.get("/v1/me", headers=auth_headers)
    assert me.status_code == 200
    body = me.json()
    assert body["id"] == str(user_id)
    assert body["display_name"] == "Abhishek"
    assert body["language"] == "mr"
    assert body["phone"] == "919800000000"


async def test_push_is_idempotent_on_client_mutation_id(
    client: httpx.AsyncClient, auth_headers: dict[str, str], user_id: uuid.UUID
) -> None:
    m = profile_mutation(user_id)
    await push(client, auth_headers, m)
    [again] = await push(client, auth_headers, m)
    assert again["status"] == "duplicate"


async def test_last_writer_wins_and_stale_writes_are_recorded_not_applied(
    client: httpx.AsyncClient, auth_headers: dict[str, str], user_id: uuid.UUID
) -> None:
    newer = profile_mutation(user_id, updated_at="2026-10-02T06:00:00Z", display_name="New")
    older = profile_mutation(user_id, updated_at="2026-10-01T06:00:00Z", display_name="Old")
    results = await push(client, auth_headers, newer, older)
    assert [r["status"] for r in results] == ["applied", "stale"]
    me = (await client.get("/v1/me", headers=auth_headers)).json()
    assert me["display_name"] == "New"


async def test_rejects_unknown_entity_and_invalid_payload_per_mutation(
    client: httpx.AsyncClient, auth_headers: dict[str, str], user_id: uuid.UUID
) -> None:
    unknown = profile_mutation(user_id) | {"entity": "spaceship"}
    bad_language = profile_mutation(user_id, language="x" * 40)
    good = profile_mutation(user_id)
    results = await push(client, auth_headers, unknown, bad_language, good)
    assert [r["status"] for r in results] == ["rejected", "rejected", "applied"]
    assert results[0]["error"] == "unknown_entity"
    assert results[1]["error"] == "invalid_payload"


async def test_cannot_write_another_farmers_profile(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    [result] = await push(client, auth_headers, profile_mutation(uuid.uuid4()))
    assert result["status"] == "rejected"
    assert result["error"] == "forbidden"


async def test_delete_op_not_supported_for_profile(
    client: httpx.AsyncClient, auth_headers: dict[str, str], user_id: uuid.UUID
) -> None:
    m = profile_mutation(user_id) | {"op": "delete"}
    [result] = await push(client, auth_headers, m)
    assert result == {
        "client_mutation_id": m["client_mutation_id"],
        "status": "rejected",
        "error": "unsupported_op",
    }


async def test_batch_size_is_limited(
    client: httpx.AsyncClient, auth_headers: dict[str, str], user_id: uuid.UUID
) -> None:
    batch = [profile_mutation(user_id) for _ in range(201)]
    resp = await client.post("/v1/sync/push", json={"mutations": batch}, headers=auth_headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_pull_returns_changes_after_cursor_only_for_owner(
    client: httpx.AsyncClient, auth_headers: dict[str, str], user_id: uuid.UUID
) -> None:
    other = uuid.uuid4()
    other_headers = {"Authorization": f"Bearer {make_token(other)}"}
    await push(client, other_headers, profile_mutation(other, display_name="Other"))
    await push(client, auth_headers, profile_mutation(user_id))

    first = (await client.get("/v1/sync/pull", headers=auth_headers)).json()
    assert [c["entity_id"] for c in first["changes"]] == [str(user_id)]
    assert first["changes"][0]["data"]["display_name"] == "Abhishek"
    cursor = first["cursor"]
    assert cursor > 0

    empty = (
        await client.get("/v1/sync/pull", params={"since": cursor}, headers=auth_headers)
    ).json()
    assert empty == {"changes": [], "cursor": cursor}

    await push(
        client,
        auth_headers,
        profile_mutation(user_id, updated_at="2026-10-05T00:00:00Z", village="Katol"),
    )
    later = (
        await client.get("/v1/sync/pull", params={"since": cursor}, headers=auth_headers)
    ).json()
    assert later["changes"][0]["data"]["village"] == "Katol"
    assert later["cursor"] > cursor
