"""Types shared by all source adapters and the pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

WorkSetup = Literal["remote", "hybrid", "onsite", "unspecified"]
JobType = Literal["full_time", "part_time", "contract", "freelance", "unspecified"]
SalaryPeriod = Literal["hour", "day", "week", "month", "year"]


@dataclass(frozen=True)
class Page:
    """One raw HTTP response body, exactly as fetched. Saved verbatim as a test fixture."""

    url: str
    text: str


@dataclass(frozen=True)
class RawItem:
    """One posting's raw payload, stored in raw_postings before any parsing."""

    external_id: str
    url: str
    payload: str


class ParsedPosting(BaseModel):
    """What an adapter's parse() returns: only facts the source actually states.

    Derived fields (seniority, PHP monthly salary, ph_eligible, skills) are computed later
    by scraper/normalize/ and must never be guessed here.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    external_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    company_name: str | None = None
    source_url: str
    location_text: str | None = None
    description: str | None = None
    posted_at: datetime | None = None
    # Source-stated work setup / job type (from a structured field), else "unspecified".
    work_setup: WorkSetup = "unspecified"
    job_type: JobType = "unspecified"
    # Salary exactly as the source states it; conversion to PHP/month happens in normalize.
    salary_raw: str | None = None
    salary_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    salary_period: SalaryPeriod | None = None
    salary_min: float | None = Field(default=None, gt=0)
    salary_max: float | None = Field(default=None, gt=0)
    tags: list[str] = Field(default_factory=list)

    @field_validator("source_url")
    @classmethod
    def _http_url(cls, v: str) -> str:
        if not v.startswith(("https://", "http://")):
            raise ValueError("source_url must be an absolute http(s) URL")
        return v

    @field_validator("salary_max")
    @classmethod
    def _min_le_max(cls, v: float | None, info) -> float | None:
        lo = info.data.get("salary_min")
        if v is not None and lo is not None and lo > v:
            raise ValueError("salary_min > salary_max")
        return v
