"""Seed a minimal dev dataset.  Run: ``uv run python -m scripts.seed`` (or ``make seed``).

Idempotent: does nothing if the dev user already exists.
"""

from __future__ import annotations

import asyncio

from argon2 import PasswordHasher
from sqlalchemy import select

from app.db.session import get_engine, get_sessionmaker
from app.models import JobPreference, JobSource, Resume, ResumeVersion, User
from app.models.enums import ResumeVersionSource

DEV_EMAIL = "dev@career-copilot.local"


async def seed() -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session, session.begin():
        existing = (
            await session.execute(select(User).where(User.email == DEV_EMAIL))
        ).scalar_one_or_none()
        if existing is not None:
            print(f"user {DEV_EMAIL} already exists ({existing.id}) — nothing to do")
            return

        user = User(
            email=DEV_EMAIL,
            password_hash=PasswordHasher().hash("devpassword"),
            display_name="Dev User",
        )
        user.preferences = JobPreference(
            desired_roles=["Backend Engineer", "Platform Engineer"],
            locations=["Tokyo", "Remote"],
            employment_types=["full_time"],
            salary_min=8_000_000,
            remote_required=False,
        )
        resume = Resume(user=user, label="Base résumé")
        resume.versions.append(
            ResumeVersion(
                user=user,
                version_no=1,
                source=ResumeVersionSource.FORM,
                raw_text="Backend engineer with 6 years of Python/FastAPI/PostgreSQL on AWS.",
                structured={
                    "summary": "Backend engineer, 6y.",
                    "skills": ["python", "fastapi", "postgresql", "aws"],
                },
            )
        )
        user.resumes.append(resume)
        user.job_sources.append(
            JobSource(
                user=user,
                url="https://boards.greenhouse.io/example",
                label="Example Corp",
            )
        )
        session.add(user)

    print(f"seeded {DEV_EMAIL}")
    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(seed())
