from __future__ import annotations

from httpx import AsyncClient

from app.models import User
from tests.fakes import RecordingQueue


async def test_register_source_enqueues_a_fetch(
    client: AsyncClient, signed_in: User, task_queue: RecordingQueue
) -> None:
    r = await client.post(
        "/api/v1/job-sources",
        json={"url": "https://boards.greenhouse.io/acme", "label": "Acme"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "active"
    assert body["robots_state"] == "unknown"
    assert [m.task for m in task_queue.messages] == ["job_source.fetch"]
    assert task_queue.messages[0].payload["source_id"] == body["id"]


async def test_register_rejects_non_http_url(client: AsyncClient, signed_in: User) -> None:
    r = await client.post("/api/v1/job-sources", json={"url": "ftp://x/y"})
    assert r.status_code == 422


async def test_register_rejects_duplicate_url(client: AsyncClient, signed_in: User) -> None:
    payload = {"url": "https://jobs.lever.co/acme"}
    assert (await client.post("/api/v1/job-sources", json=payload)).status_code == 201
    dup = await client.post("/api/v1/job-sources", json=payload)
    assert dup.status_code == 422


async def test_list_get_pause_resume_delete(
    client: AsyncClient, signed_in: User, task_queue: RecordingQueue
) -> None:
    created = (
        await client.post("/api/v1/job-sources", json={"url": "https://acme.example/careers"})
    ).json()
    sid = created["id"]

    listed = (await client.get("/api/v1/job-sources")).json()
    assert [s["id"] for s in listed] == [sid]

    paused = (await client.post(f"/api/v1/job-sources/{sid}/pause")).json()
    assert paused["status"] == "paused"

    # can't force-fetch a paused source
    assert (await client.post(f"/api/v1/job-sources/{sid}/fetch")).status_code == 422

    resumed = (await client.post(f"/api/v1/job-sources/{sid}/resume")).json()
    assert resumed["status"] == "active"

    task_queue.messages.clear()
    assert (await client.post(f"/api/v1/job-sources/{sid}/fetch")).status_code == 200
    assert [m.task for m in task_queue.messages] == ["job_source.fetch"]

    assert (await client.delete(f"/api/v1/job-sources/{sid}")).status_code == 204
    assert (await client.get(f"/api/v1/job-sources/{sid}")).status_code == 404


async def test_sources_are_per_user(client: AsyncClient, signed_in: User) -> None:
    await client.post("/api/v1/job-sources", json={"url": "https://acme.example/careers"})

    client.cookies.clear()
    client.headers.pop("x-csrf-token", None)
    assert (await client.get("/api/v1/job-sources")).status_code == 401
