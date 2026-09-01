from __future__ import annotations

from typing import Any

from app.models import JobPreference
from app.repositories.base import UserScopedRepository


class PreferenceRepository(UserScopedRepository):
    async def get(self) -> JobPreference | None:
        result = await self.session.execute(self._scoped(JobPreference))
        return result.scalar_one_or_none()

    async def upsert(self, data: dict[str, Any]) -> JobPreference:
        prefs = await self.get()
        if prefs is None:
            prefs = JobPreference(user_id=self.user_id, **data)
            self.session.add(prefs)
        else:
            for key, value in data.items():
                setattr(prefs, key, value)
        await self.session.flush()
        return prefs
