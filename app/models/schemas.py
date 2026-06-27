from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class AssetType(str, Enum):
    domain = "domain"
    subdomain = "subdomain"
    ip_address = "ip_address"
    service = "service"
    certificate = "certificate"
    technology = "technology"


class AssetStatus(str, Enum):
    active = "active"
    stale = "stale"
    archived = "archived"


class AssetCreate(BaseModel):
    id: Optional[str] = None
    type: AssetType
    value: str
    status: AssetStatus = AssetStatus.active
    source: str
    tags: List[str] = []
    metadata: dict = {}

    @field_validator("value")
    @classmethod
    def value_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("value cannot be empty")
        return v.strip().lower()


class AssetOut(BaseModel):
    id: str
    type: AssetType
    value: str
    status: AssetStatus
    first_seen: datetime
    last_seen: datetime
    source: str
    tags: List[str]
    metadata: dict

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_custom(cls, obj):
        return cls(
            id=obj.id,
            type=obj.type,
            value=obj.value,
            status=obj.status,
            first_seen=obj.first_seen,
            last_seen=obj.last_seen,
            source=obj.source,
            tags=obj.tags or [],
            metadata=obj.metadata_ or {},
        )


class ImportResult(BaseModel):
    imported: int
    updated: int
    failed: int
    errors: List[dict] = []


class AnalyzeRequest(BaseModel):
    mode: str  # nl_query | risk_score | enrich | report | agent
    input: Optional[str] = None
    asset_id: Optional[str] = None
    filters: Optional[dict] = {}
