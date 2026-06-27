from sqlalchemy import Column, String, DateTime, JSON, Enum, ForeignKey, ARRAY, Text
from sqlalchemy.orm import relationship
from app.db.database import Base
from datetime import datetime, timezone
import uuid
import enum


class AssetType(str, enum.Enum):
    domain = "domain"
    subdomain = "subdomain"
    ip_address = "ip_address"
    service = "service"
    certificate = "certificate"
    technology = "technology"


class AssetStatus(str, enum.Enum):
    active = "active"
    stale = "stale"
    archived = "archived"


class Asset(Base):
    __tablename__ = "assets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    type = Column(Enum(AssetType), nullable=False)
    value = Column(String, nullable=False)
    status = Column(Enum(AssetStatus), default=AssetStatus.active)
    first_seen = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    source = Column(String, nullable=False)
    tags = Column(ARRAY(Text), default=[])
    metadata_ = Column("metadata", JSON, default={})

    outgoing = relationship(
        "AssetRelationship",
        foreign_keys="AssetRelationship.source_id",
        back_populates="source_asset",
        cascade="all, delete",
    )
    incoming = relationship(
        "AssetRelationship",
        foreign_keys="AssetRelationship.target_id",
        back_populates="target_asset",
        cascade="all, delete",
    )


class AssetRelationship(Base):
    __tablename__ = "asset_relationships"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id = Column(String, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(String, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    relation_type = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    source_asset = relationship("Asset", foreign_keys=[source_id], back_populates="outgoing")
    target_asset = relationship("Asset", foreign_keys=[target_id], back_populates="incoming")
