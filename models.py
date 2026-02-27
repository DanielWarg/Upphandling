"""Pydantic models for procurement data."""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, computed_field, field_validator, model_validator


class TenderRecord(BaseModel):
    """Normalized procurement record used by all scrapers and db.py."""

    source: Literal["ted", "mercell", "kommers", "eavrop"]
    source_id: str
    title: str
    buyer: str | None = None
    geography: str | None = None
    cpv_codes: str | None = None
    procedure_type: str | None = None
    published_date: str | None = None
    deadline: str | None = None
    estimated_value: float | None = None
    currency: str | None = "SEK"
    status: str | None = "published"
    url: str | None = None
    description: str | None = None
    score: int = 0
    score_rationale: str | None = None

    @field_validator("title", "buyer", "geography", "cpv_codes", "procedure_type",
                     "url", "score_rationale", mode="before")
    @classmethod
    def strip_whitespace(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v

    @field_validator("published_date", "deadline", mode="before")
    @classmethod
    def coerce_date(cls, v) -> str | None:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.date().isoformat()
        if isinstance(v, date):
            return v.isoformat()
        if isinstance(v, str):
            v = v.strip()[:10]
            return v if v else None
        return str(v)[:10]

    @field_validator("description", mode="before")
    @classmethod
    def truncate_description(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            v = v.strip()
            return v[:2000] if v else None
        return v

    @field_validator("estimated_value", mode="before")
    @classmethod
    def coerce_value(cls, v) -> float | None:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v.replace(",", ".").replace(" ", ""))
            except ValueError:
                return None
        return None

    @model_validator(mode="after")
    def ensure_source_id(self):
        if not self.source_id:
            raise ValueError("source_id cannot be empty")
        if not self.title:
            raise ValueError("title cannot be empty")
        return self

    @computed_field
    @property
    def hash_fingerprint(self) -> str:
        """SHA-256 fingerprint based on title|buyer|deadline for dedup."""
        parts = "|".join([
            (self.title or "").lower(),
            (self.buyer or "").lower(),
            (self.deadline or ""),
        ])
        return hashlib.sha256(parts.encode()).hexdigest()[:16]

    def to_db_dict(self) -> dict:
        """Convert to dict suitable for SQLite insertion via db.upsert_procurement."""
        return {
            "source": self.source,
            "source_id": self.source_id,
            "title": self.title,
            "buyer": self.buyer,
            "geography": self.geography,
            "cpv_codes": self.cpv_codes,
            "procedure_type": self.procedure_type,
            "published_date": self.published_date,
            "deadline": self.deadline,
            "estimated_value": self.estimated_value,
            "currency": self.currency,
            "status": self.status,
            "url": self.url,
            "description": self.description,
            "score": self.score,
            "score_rationale": self.score_rationale,
        }
