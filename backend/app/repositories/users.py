"""User identity repository (not user-scoped — this is the identity lookup)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import normalize_email
from app.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == normalize_email(email))
        )
        return result.scalar_one_or_none()

    async def get_or_create_verified(self, email: str) -> User:
        """Called after a successful OTP — receiving the code proves email control."""
        user = await self.get_by_email(email)
        if user is None:
            user = User(email=normalize_email(email), email_verified_at=datetime.now(UTC))
            self.session.add(user)
            await self.session.flush()
        elif user.email_verified_at is None:
            user.email_verified_at = datetime.now(UTC)
        return user
