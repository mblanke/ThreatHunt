"""SQLAlchemy ORM models for ThreatHunt.

All persistent entities: datasets, hunts, conversations, annotations,
hypotheses, enrichment results, users, and AI analysis tables.
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


# -- Users ---

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="analyst")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    hunts: Mapped[list["Hunt"]] = relationship(back_populates="owner", lazy="selectin")
    annotations: Mapped[list["Annotation"]] = relationship(back_populates="author", lazy="selectin")


# -- Hunts ---

class Hunt(Base):
    __tablename__ = "hunts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    owner_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    owner: Mapped[Optional["User"]] = relationship(back_populates="hunts", lazy="selectin")
    datasets: Mapped[list["Dataset"]] = relationship(back_populates="hunt", lazy="selectin")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="hunt", lazy="selectin")
    hypotheses: Mapped[list["Hypothesis"]] = relationship(back_populates="hunt", lazy="selectin")
    host_profiles: Mapped[list["HostProfile"]] = relationship(back_populates="hunt", lazy="noload")
    reports: Mapped[list["HuntReport"]] = relationship(back_populates="hunt", lazy="noload")


# -- Datasets ---

class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    source_tool: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    column_schema: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    normalized_columns: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ioc_columns: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    encoding: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    delimiter: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    time_range_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    time_range_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # New Phase 1-2 columns
    processing_status: Mapped[str] = mapped_column(String(20), default="ready")
    artifact_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    hunt_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("hunts.id"), nullable=True
    )
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    hunt: Mapped[Optional["Hunt"]] = relationship(back_populates="datasets", lazy="selectin")
    rows: Mapped[list["DatasetRow"]] = relationship(
        back_populates="dataset", lazy="noload", cascade="all, delete-orphan"
    )
    triage_results: Mapped[list["TriageResult"]] = relationship(
        back_populates="dataset", lazy="noload", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_datasets_hunt", "hunt_id"),
        Index("ix_datasets_status", "processing_status"),
    )


class DatasetRow(Base):
    __tablename__ = "dataset_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    normalized_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    dataset: Mapped["Dataset"] = relationship(back_populates="rows")
    annotations: Mapped[list["Annotation"]] = relationship(
        back_populates="row", lazy="noload"
    )

    __table_args__ = (
        Index("ix_dataset_rows_dataset", "dataset_id"),
        Index("ix_dataset_rows_dataset_idx", "dataset_id", "row_index"),
    )


# -- Conversations ---

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
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    node_used: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    __table_args__ = (
        Index("ix_messages_conversation", "conversation_id"),
    )


# -- Annotations ---

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
    severity: Mapped[str] = mapped_column(String(16), default="info")
    tag: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    highlight_color: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    row: Mapped[Optional["DatasetRow"]] = relationship(back_populates="annotations")
    author: Mapped[Optional["User"]] = relationship(back_populates="annotations")

    __table_args__ = (
        Index("ix_annotations_dataset", "dataset_id"),
        Index("ix_annotations_row", "row_id"),
    )


# -- Hypotheses ---

class Hypothesis(Base):
    __tablename__ = "hypotheses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    hunt_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("hunts.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mitre_technique: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    evidence_row_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    evidence_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    hunt: Mapped[Optional["Hunt"]] = relationship(back_populates="hypotheses", lazy="selectin")

    __table_args__ = (
        Index("ix_hypotheses_hunt", "hunt_id"),
    )


# -- Enrichment Results ---

class EnrichmentResult(Base):
    __tablename__ = "enrichment_results"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    ioc_value: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    ioc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    verdict: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
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


# -- AUP Keyword Themes & Keywords ---

class KeywordTheme(Base):
    __tablename__ = "keyword_themes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    color: Mapped[str] = mapped_column(String(16), default="#9e9e9e")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    keywords: Mapped[list["Keyword"]] = relationship(
        back_populates="theme", lazy="selectin", cascade="all, delete-orphan"
    )


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theme_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("keyword_themes.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[str] = mapped_column(String(256), nullable=False)
    is_regex: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    theme: Mapped["KeywordTheme"] = relationship(back_populates="keywords")

    __table_args__ = (
        Index("ix_keywords_theme", "theme_id"),
        Index("ix_keywords_value", "value"),
    )


# -- AI Analysis Tables (Phase 2) ---

class TriageResult(Base):
    __tablename__ = "triage_results"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    dataset_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    row_start: Mapped[int] = mapped_column(Integer, nullable=False)
    row_end: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    verdict: Mapped[str] = mapped_column(String(20), default="pending")
    findings: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    suspicious_indicators: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    mitre_techniques: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    node_used: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    dataset: Mapped["Dataset"] = relationship(back_populates="triage_results")


class HostProfile(Base):
    __tablename__ = "host_profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    hunt_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("hunts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hostname: Mapped[str] = mapped_column(String(256), nullable=False)
    fqdn: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[str] = mapped_column(String(20), default="unknown")
    artifact_summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    timeline_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suspicious_findings: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    mitre_techniques: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    llm_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    node_used: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    hunt: Mapped["Hunt"] = relationship(back_populates="host_profiles")


class HuntReport(Base):
    __tablename__ = "hunt_reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    hunt_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("hunts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    exec_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    full_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    findings: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    recommendations: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    mitre_mapping: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ioc_table: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    host_risk_summary: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    models_used: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    generation_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    hunt: Mapped["Hunt"] = relationship(back_populates="reports")


class AnomalyResult(Base):
    __tablename__ = "anomaly_results"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    dataset_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    row_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("dataset_rows.id", ondelete="CASCADE"), nullable=True
    )
    anomaly_score: Mapped[float] = mapped_column(Float, default=0.0)
    distance_from_centroid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cluster_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_outlier: Mapped[bool] = mapped_column(Boolean, default=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)