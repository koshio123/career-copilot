from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import JobPreference


class PreferenceIn(BaseModel):
    desired_roles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    employment_types: list[str] = Field(default_factory=list)
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    remote_required: bool = False
    target_start: date | None = None

    @model_validator(mode="after")
    def _salary_order(self) -> PreferenceIn:
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min must not exceed salary_max")
        return self


class PreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    desired_roles: list[str]
    locations: list[str]
    employment_types: list[str]
    salary_min: int | None
    salary_max: int | None
    remote_required: bool
    target_start: date | None

    @classmethod
    def of(cls, prefs: JobPreference | None) -> PreferenceOut:
        if prefs is None:
            return cls(
                desired_roles=[],
                locations=[],
                employment_types=[],
                salary_min=None,
                salary_max=None,
                remote_required=False,
                target_start=None,
            )
        return cls.model_validate(prefs)
