from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobPosting, User

MANUAL = {
    "company_name": "株式会社Acme",
    "title": "Senior Backend Engineer",
    "location": "Tokyo",
    "remote": True,
    "salary_min": 8_000_000,
    "salary_max": 12_000_000,
    "required_skills": ["Python", "PostgreSQL"],
    "description": "Build the thing.",
}


async def test_add_manual_job(client: AsyncClient, signed_in: User) -> None:
    r = await client.post("/api/v1/jobs", json=MANUAL)
    assert r.status_code == 201
    body = r.json()
    assert body["company_name"] == "株式会社Acme"
    assert body["canonical_title"] == "Senior Backend Engineer"
    assert body["source_type"] == "manual"
    assert body["structured"]["required_skills"] == ["Python", "PostgreSQL"]


async def test_duplicate_manual_job_is_rejected(client: AsyncClient, signed_in: User) -> None:
    assert (await client.post("/api/v1/jobs", json=MANUAL)).status_code == 201
    dup = await client.post(
        "/api/v1/jobs",
        json={**MANUAL, "company_name": "Acme Inc.", "title": "senior backend engineer"},
    )
    assert dup.status_code == 422


async def test_reject_bad_salary_range(client: AsyncClient, signed_in: User) -> None:
    r = await client.post(
        "/api/v1/jobs",
        json={"company_name": "X", "title": "Y", "salary_min": 9, "salary_max": 1},
    )
    assert r.status_code == 422


async def test_list_puts_scored_jobs_first(
    client: AsyncClient, signed_in: User, db: AsyncSession
) -> None:
    await client.post("/api/v1/jobs", json={"company_name": "A", "title": "Role A"})
    await client.post("/api/v1/jobs", json={"company_name": "B", "title": "Role B"})

    b = (await db.execute(select(JobPosting).where(JobPosting.company_name == "B"))).scalar_one()
    b.match_score = Decimal("72.5")
    await db.flush()

    listed = (await client.get("/api/v1/jobs")).json()
    assert listed[0]["company_name"] == "B"
    assert listed[0]["match_score"] == 72.5
    assert {j["company_name"] for j in listed} == {"A", "B"}


async def test_update_status_and_bookmark(client: AsyncClient, signed_in: User) -> None:
    jid = (await client.post("/api/v1/jobs", json=MANUAL)).json()["id"]
    patched = (
        await client.patch(f"/api/v1/jobs/{jid}", json={"status": "interested", "bookmarked": True})
    ).json()
    assert patched["status"] == "interested"
    assert patched["bookmarked"] is True

    assert (await client.delete(f"/api/v1/jobs/{jid}")).status_code == 204
    assert (await client.get(f"/api/v1/jobs/{jid}")).status_code == 404
