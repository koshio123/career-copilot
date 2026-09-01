from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CsrfGuard, CurrentUser, DbSession
from app.repositories.preferences import PreferenceRepository
from app.schemas.preference import PreferenceIn, PreferenceOut

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("")
async def get_preferences(user: CurrentUser, db: DbSession) -> PreferenceOut:
    prefs = await PreferenceRepository(db, user_id=user.id).get()
    return PreferenceOut.of(prefs)


@router.put("", dependencies=[CsrfGuard])
async def put_preferences(body: PreferenceIn, user: CurrentUser, db: DbSession) -> PreferenceOut:
    prefs = await PreferenceRepository(db, user_id=user.id).upsert(body.model_dump())
    return PreferenceOut.of(prefs)
