"""Evidence-backed feature hints, independent of ASVS applicability decisions."""
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

FeatureName = Literal['authentication', 'file_upload', 'oauth_oidc', 'websocket', 'graphql']
DetectionStatus = Literal['observed', 'suspected', 'not_observed']


class Evidence(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reference: str  # JSON pointer into the immutable source crawl snapshot
    observation_id: str | None = None
    source_url: str
    url: str
    timestamp: datetime
    summary: str
    confidence: float = Field(ge=0, le=1)
    direct: bool = False


class FeatureDetection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    feature: FeatureName
    status: DetectionStatus
    confidence: float = Field(ge=0, le=1)
    evidence: list[Evidence]
    source_url: str
    detected_at: datetime
    limitations: list[str]

    @model_validator(mode='after')
    def evidence_required(self) -> 'FeatureDetection':
        if self.status == 'not_observed':
            if self.evidence or self.confidence != 0:
                raise ValueError('Not observed requires no evidence and zero confidence')
        elif not self.evidence:
            raise ValueError('Positive hints require evidence')
        return self


class DetectionRun(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(default_factory=lambda: str(uuid4()))
    crawl_id: str
    crawl_sha256: str
    detector_version: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    features: list[FeatureDetection]
    limitations: list[str]
