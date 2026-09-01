from __future__ import annotations

from httpx import AsyncClient

from app.models import User


async def test_preferences_default_to_empty(client: AsyncClient, signed_in: User) -> None:
    r = await client.get("/api/v1/preferences")
    assert r.status_code == 200
    assert r.json() == {
        "desired_roles": [],
        "locations": [],
        "employment_types": [],
        "salary_min": None,
        "salary_max": None,
        "remote_required": False,
        "target_start": None,
    }


async def test_preferences_put_then_get(client: AsyncClient, signed_in: User) -> None:
    payload = {
        "desired_roles": ["Backend Engineer"],
        "locations": ["Tokyo", "Remote"],
        "employment_types": ["full_time"],
        "salary_min": 8_000_000,
        "salary_max": 12_000_000,
        "remote_required": True,
        "target_start": "2026-10-01",
    }
    put = await client.put("/api/v1/preferences", json=payload)
    assert put.status_code == 200

    got = (await client.get("/api/v1/preferences")).json()
    assert got == payload

    # update is idempotent, not additive
    await client.put("/api/v1/preferences", json={**payload, "desired_roles": ["SRE"]})
    assert (await client.get("/api/v1/preferences")).json()["desired_roles"] == ["SRE"]


async def test_preferences_reject_bad_salary_range(client: AsyncClient, signed_in: User) -> None:
    r = await client.put(
        "/api/v1/preferences", json={"salary_min": 10_000_000, "salary_max": 5_000_000}
    )
    assert r.status_code == 422
