from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.user import UserOut

router = APIRouter(tags=["users"])


@router.get("/me")
async def me(user: CurrentUser) -> UserOut:
    return UserOut.of(user)
