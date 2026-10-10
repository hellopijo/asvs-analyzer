"""Crawl configuration and sanitized observations; no applicability decisions."""
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from asvs_analyzer.crawler.scope import Scope, canonical_url


class CrawlConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    target: str
    authorized: bool = False
    scope_path: str = "/"
    max_depth: int = Field(default=3, ge=0, le=20)
    max_pages: int = Field(default=50, ge=1, le=10000)
    max_requests: int = Field(default=500, ge=1, le=100000)
    timeout_ms: int = Field(default=10000, ge=100, le=120000)
    duration_seconds: int = Field(default=120, ge=1, le=86400)
    delay_ms: int = Field(default=200, ge=0, le=60000)
    settle_ms: int = Field(default=300, ge=0, le=10000)
    storage_state: Path | None = Field(default=None, exclude=True)
    exclude_paths: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_scope(self) -> "CrawlConfig":
        if not self.authorized:
            raise ValueError("Explicit authorization is required")
        self.target = canonical_url(self.target)
        Scope(self.target, self.scope_path)
        for path in self.exclude_paths:
            if not path.startswith("/"):
                raise ValueError("Excluded paths must start with /")
        return self


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    kind: Literal["request", "response", "websocket", "cookie"]
    source_url: str
    url: str
    method: str | None = None
    status: int | None = None
    blocked_reason: str | None = None
    attributes: dict[str, str | bool | float] = Field(default_factory=dict)


class FormObservation(BaseModel):
    action: str
    method: str
    enctype: str
    input_types: list[str]


class PageObservation(BaseModel):
    url: str
    depth: int
    status: int | None = None
    title: str = "[OMITTED: may contain sensitive data]"
    links: list[str] = Field(default_factory=list)
    forms: list[FormObservation] = Field(default_factory=list)
    input_types: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class CrawlRun(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    target: str
    scope_path: str
    pages: list[PageObservation] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    limits: dict[str, int] = Field(default_factory=dict)
    stop_reason: str = "complete"
    requests_sent: int = 0
    limitations: list[str] = Field(default_factory=list)
