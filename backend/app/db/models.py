"""SQLAlchemy ORM models for ThreatHunt.

All persistent entities: datasets, hunts, conversations, annotations,
hypotheses, enrichment results, and users.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .engine import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


# ── Users ──────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="analyst")  # analyst | admin | viewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # relationships
    hunts: Mapped[list["Hunt"]] = relationship(back_populates="owner", lazy="selectin")
    annotations: Mapped[list["Annotation"]] = relationship(back_populates="author", lazy="selectin")


# ── Hunts ──────────────────────────────────────────────────────────────


class Hunt(Base):
    __tablename__ = "hunts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")  # active | closed | archived
    owner_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # relationships
    owner: Mapped[Optional["User"]] = relationship(back_populates="hunts", lazy="selectin")
    datasets: Mapped[list["Dataset"]] = relationship(back_populates="hunt", lazy="selectin")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="hunt", lazy="selectin")
    hypotheses: Mapped[list["Hypothesis"]] = relationship(back_populates="hunt", lazy="selectin")


# ── Datasets ───────────────────────────────────────────────────────────


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    source_tool: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # velociraptor, etc.
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    column_schema: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    normalized_columns: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ioc_columns: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # auto-detected IOC columns
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    encoding: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    delimiter: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    time_range_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    time_range_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    hunt_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("hunts.id"), nullable=True
    )
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # relationships
    hunt: Mapped[Optional["Hunt"]] = relationship(back_populates="datasets", lazy="selectin")
    rows: Mapped[list["DatasetRow"]] = relationship(
        back_populates="dataset", lazy="noload", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_datasets_hunt", "hunt_id"),
    )


class DatasetRow(Base):
    """Individual row from a CSV dataset, stored as JSON blob."""
    __tablename__ = "dataset_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    normalized_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # relationships
    dataset: Mapped["Dataset"] = relationship(back_populates="rows")
    annotations: Mapped[list["Annotation"]] = relationship(
        back_populates="row", lazy="noload"
    )

    __table_args__ = (
        Index("ix_dataset_rows_dataset", "dataset_id"),
        Index("ix_dataset_rows_dataset_idx", "dataset_id", "row_index"),
    )


# ── Conversations ─────────────────────────────────────────────────────


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    title: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    hunt_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("hunts.id"), nullable=True
    )
    dataset_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("datasets.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # relationships
    hunt: Mapped[Optional["Hunt"]] = relationship(back_populates="conversations", lazy="selectin")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", lazy="selectin", cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | agent | system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    node_used: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # wile | roadrunner | cluster
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    __table_args__ = (
        Index("ix_messages_conversation", "conversation_id"),
    )


# ── Annotations ───────────────────────────────────────────────────────


class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    row_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("dataset_rows.id", ondelete="SET NULL"), nullable=True
    )
    dataset_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("datasets.id"), nullable=True
    )
    author_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(
        String(16), default="info"
    )  # info | low | medium | high | critical
    tag: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )  # suspicious | benign | needs-review
    highlight_color: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # relationships
    row: Mapped[Optional["DatasetRow"]] = relationship(back_populates="annotations")
    author: Mapped[Optional["User"]] = relationship(back_populates="annotations")

    __table_args__ = (
        Index("ix_annotations_dataset", "dataset_id"),
        Index("ix_annotations_row", "row_id"),
    )


# ── Hypotheses ────────────────────────────────────────────────────────


class Hypothesis(Base):
    __tablename__ = "hypotheses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    hunt_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("hunts.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mitre_technique: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), default="draft"
    )  # draft | active | confirmed | rejected
    evidence_row_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    evidence_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # relationships
    hunt: Mapped[Optional["Hunt"]] = relationship(back_populates="hypotheses", lazy="selectin")

    __table_args__ = (
        Index("ix_hypotheses_hunt", "hunt_id"),
    )


# ── Enrichment Results ────────────────────────────────────────────────


class EnrichmentResult(Base):
    __tablename__ = "enrichment_results"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    ioc_value: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    ioc_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # ip | hash_md5 | hash_sha1 | hash_sha256 | domain | url
    source: Mapped[str] = mapped_column(String(32), nullable=False)  # virustotal | abuseipdb | shodan | ai
    verdict: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True
    )  # clean | suspicious | malicious | unknown
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dataset_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("datasets.id"), nullable=True
    )
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_enrichment_ioc_source", "ioc_value", "source"),
    )


# ── AUP Keyword Themes & Keywords ────────────────────────────────────


class KeywordTheme(Base):
    """A named category of keywords for AUP scanning (e.g. gambling, gaming)."""
    __tablename__ = "keyword_themes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    color: Mapped[str] = mapped_column(String(16), default="#9e9e9e")  # hex chip color
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)  # seed-provided
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # relationships
    keywords: Mapped[list["Keyword"]] = relationship(
        back_populates="theme", lazy="selectin", cascade="all, delete-orphan"
    )


class Keyword(Base):
    """Individual keyword / pattern belonging to a theme."""
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theme_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("keyword_themes.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[str] = mapped_column(String(256), nullable=False)
    is_regex: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # relationships
    theme: Mapped["KeywordTheme"] = relationship(back_populates="keywords")

    __table_args__ = (
        Index("ix_keywords_theme", "theme_id"),
        Index("ix_keywords_value", "value"),
    )
