"""SQLAlchemy 2.0 ORM data models for the ScholarPilot production schema."""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from app.db.base import Base, GUID, TimestampedUUIDMixin


# Portable JSON type: JSONB on Postgres, JSON on SQLite
JSONType = JSON().with_variant(JSONB, "postgresql")


class User(Base, TimestampedUUIDMixin):
    """User account model."""
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Africa/Lagos", nullable=False)
    mode: Mapped[str] = mapped_column(String(32), default="autopilot", nullable=False)  # autopilot, review
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)  # active, suspended, deleted

    # Relationships
    profile: Mapped[Optional["Profile"]] = relationship("Profile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    matches: Mapped[List["Match"]] = relationship("Match", back_populates="user", cascade="all, delete-orphan")
    applications: Mapped[List["Application"]] = relationship("Application", back_populates="user", cascade="all, delete-orphan")
    api_keys: Mapped[List["ApiKey"]] = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    webhooks: Mapped[List["Webhook"]] = relationship("Webhook", back_populates="user", cascade="all, delete-orphan")


class Profile(Base, TimestampedUUIDMixin):
    """User Profile Vault storing verified facts, history, and preferences."""
    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    personal_details: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    education_history: Mapped[List[Dict[str, Any]]] = mapped_column(JSONType, default=list, nullable=False)
    grades: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    test_scores: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    achievements: Mapped[List[Dict[str, Any]]] = mapped_column(JSONType, default=list, nullable=False)
    financial_need_info: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    target_countries: Mapped[List[str]] = mapped_column(JSONType, default=list, nullable=False)
    target_fields_of_study: Mapped[List[str]] = mapped_column(JSONType, default=list, nullable=False)
    completeness_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="profile")


class Document(Base, TimestampedUUIDMixin):
    """Uploaded academic or personal document reference."""
    __tablename__ = "documents"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)  # cv, transcript, essay, recommendation, other
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="documents")


class Scholarship(Base, TimestampedUUIDMixin):
    """Cataloged scholarship opportunity."""
    __tablename__ = "scholarships"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(128), nullable=False)
    level: Mapped[str] = mapped_column(String(64), nullable=False)  # undergraduate, masters, phd
    field: Mapped[str] = mapped_column(String(128), nullable=False)
    amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    currency: Mapped[str] = mapped_column(String(16), default="USD", nullable=False)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    eligibility_rules: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    application_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    requires_essay: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[str] = mapped_column(String(255), default="catalog", nullable=False)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    matches: Mapped[List["Match"]] = relationship("Match", back_populates="scholarship", cascade="all, delete-orphan")
    applications: Mapped[List["Application"]] = relationship("Application", back_populates="scholarship", cascade="all, delete-orphan")


class Match(Base, TimestampedUUIDMixin):
    """Ranked match result between a user and scholarship."""
    __tablename__ = "matches"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    scholarship_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("scholarships.id", ondelete="CASCADE"), index=True, nullable=False)
    fit_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    urgency_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reasons: Mapped[List[str]] = mapped_column(JSONType, default=list, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="matches")
    scholarship: Mapped["Scholarship"] = relationship("Scholarship", back_populates="matches")


class Application(Base, TimestampedUUIDMixin):
    """Tracked scholarship application lifecycle."""
    __tablename__ = "applications"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    scholarship_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("scholarships.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="discovered", nullable=False)
    mode_used: Mapped[str] = mapped_column(String(32), default="autopilot", nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmation_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("idx_app_user_status", "user_id", "status"),
        Index("idx_app_scholarship_id", "scholarship_id"),
    )

    user: Mapped["User"] = relationship("User", back_populates="applications")
    scholarship: Mapped["Scholarship"] = relationship("Scholarship", back_populates="applications")
    events: Mapped[List["ApplicationEvent"]] = relationship("ApplicationEvent", back_populates="application", cascade="all, delete-orphan")
    drafts: Mapped[List["Draft"]] = relationship("Draft", back_populates="application", cascade="all, delete-orphan")


class ApplicationEvent(Base):
    """Append-only audit log of state changes and actions."""
    __tablename__ = "application_events"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4, index=True)
    application_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)  # agent, user, system
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False)

    application: Mapped["Application"] = relationship("Application", back_populates="events")


class Draft(Base, TimestampedUUIDMixin):
    """Generated application text or essay draft with strict source grounding facts."""
    __tablename__ = "drafts"

    application_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("applications.id", ondelete="CASCADE"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)  # essay, statement, answer, cv_summary
    content: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source_facts: Mapped[List[str]] = mapped_column(JSONType, default=list, nullable=False)

    application: Mapped["Application"] = relationship("Application", back_populates="drafts")


class Job(Base, TimestampedUUIDMixin):
    """Asynchronous background task definition for agent jobs."""
    __tablename__ = "jobs"

    type: Mapped[str] = mapped_column(String(64), nullable=False)  # match, research, edge_find, draft, submit
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)  # pending, running, completed, failed, dead_letter
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class ApiKey(Base, TimestampedUUIDMixin):
    """Developer API key storage."""
    __tablename__ = "api_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    hashed_key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    scopes: Mapped[List[str]] = mapped_column(JSONType, default=list, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="api_keys")


class Webhook(Base, TimestampedUUIDMixin):
    """Webhook subscription configuration."""
    __tablename__ = "webhooks"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    secret: Mapped[str] = mapped_column(String(255), nullable=False)
    events_subscribed: Mapped[List[str]] = mapped_column(JSONType, default=list, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="webhooks")
