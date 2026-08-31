"""Repository bases.

``UserScopedRepository`` is the base for every per-user aggregate (Phase 05+):
all of its queries go through ``_scoped()``, which always applies
``model.user_id == current user``, so a missing ownership filter can't happen by
omission.
"""

from __future__ import annotations

from typing import TypeVar
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class UserScopedRepository:
    def __init__(self, session: AsyncSession, *, user_id: UUID) -> None:
        self.session = session
        self.user_id = user_id

    def _scoped(self, model: type[ModelT]) -> Select[tuple[ModelT]]:
        return select(model).where(model.user_id == self.user_id)  # type: ignore[attr-defined]
