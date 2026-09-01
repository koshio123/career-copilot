from __future__ import annotations

from httpx import AsyncClient

from app.models import User
from tests.fakes import FakeResumeStorage, RecordingQueue

PDF = "application/pdf"


async def test_upload_url_rejects_unknown_type(client: AsyncClient, signed_in: User) -> None:
    r = await client.post(
        "/api/v1/resumes/uploads", json={"filename": "cv.txt", "content_type": "text/plain"}
    )
    assert r.status_code == 422


async def test_upload_url_returns_a_scoped_key(client: AsyncClient, signed_in: User) -> None:
    r = await client.post(
        "/api/v1/resumes/uploads", json={"filename": "cv.pdf", "content_type": PDF}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["key"].startswith(f"resumes/{signed_in.id}/")
    assert body["url"].startswith("https://")


async def test_create_from_text_enqueues_processing(
    client: AsyncClient, signed_in: User, task_queue: RecordingQueue
) -> None:
    r = await client.post(
        "/api/v1/resumes",
        json={"raw_text": "Backend engineer with six years of Python and PostgreSQL on AWS."},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["latest_version"]["status"] == "structuring"
    assert [m.task for m in task_queue.messages] == ["resume.process"]
    assert task_queue.messages[0].payload["version_id"] == body["latest_version"]["id"]


async def test_create_from_upload_checks_the_object_exists(
    client: AsyncClient,
    signed_in: User,
    storage: FakeResumeStorage,
    task_queue: RecordingQueue,
) -> None:
    up = (
        await client.post(
            "/api/v1/resumes/uploads", json={"filename": "cv.pdf", "content_type": PDF}
        )
    ).json()

    missing = await client.post("/api/v1/resumes", json={"source_key": up["key"]})
    assert missing.status_code == 422  # nothing uploaded yet

    storage.put(up["key"], b"%PDF-1.4 ...")
    ok = await client.post("/api/v1/resumes", json={"source_key": up["key"]})
    assert ok.status_code == 201
    assert ok.json()["latest_version"]["status"] == "pending"
    assert [m.task for m in task_queue.messages] == ["resume.process"]


async def test_create_rejects_someone_elses_key(client: AsyncClient, signed_in: User) -> None:
    r = await client.post(
        "/api/v1/resumes", json={"source_key": "resumes/00000000-0000-0000-0000-000000000000/x.pdf"}
    )
    assert r.status_code == 404


async def test_list_get_and_edit_round_trip(client: AsyncClient, signed_in: User) -> None:
    created = (
        await client.post(
            "/api/v1/resumes",
            json={"raw_text": "Platform engineer. Cut deploy time. Ran the on-call rotation."},
        )
    ).json()
    resume_id = created["id"]
    version_id = created["latest_version"]["id"]

    listed = (await client.get("/api/v1/resumes")).json()
    assert [r["id"] for r in listed] == [resume_id]

    detail = (await client.get(f"/api/v1/resumes/{resume_id}")).json()
    assert len(detail["versions"]) == 1

    patch = await client.patch(
        f"/api/v1/resumes/{resume_id}/versions/{version_id}",
        json={
            "structured": {
                "summary": "Platform engineer, 5y.",
                "skills": ["kubernetes", "terraform"],
                "companies": [
                    {
                        "name": "Acme",
                        "role": "SRE",
                        "achievements": [{"text": "cut deploy time 40%", "has_metric": True}],
                    }
                ],
            }
        },
    )
    assert patch.status_code == 200
    body = patch.json()
    assert body["status"] == "ready"
    assert body["structured"]["skills"] == ["kubernetes", "terraform"]


async def test_resumes_require_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/resumes")).status_code == 401
