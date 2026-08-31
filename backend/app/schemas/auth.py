from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class OtpRequestIn(BaseModel):
    email: EmailStr


class OtpVerifyIn(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")


class SessionOut(BaseModel):
    id: str
    created_at: datetime
    last_seen_at: datetime
    user_agent: str
    ip: str
    current: bool
