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
    display_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
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


# ── Cases ─────────────────────────────────────────────────────────────


class Case(Base):
    """Incident / investigation case, inspired by TheHive."""
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(16), default="medium")  # info|low|medium|high|critical
    tlp: Mapped[str] = mapped_column(String(16), default="amber")  # white|green|amber|red
    pap: Mapped[str] = mapped_column(String(16), default="amber")  # white|green|amber|red
    status: Mapped[str] = mapped_column(String(24), default="open")  # open|in-progress|resolved|closed
    priority: Mapped[int] = mapped_column(Integer, default=2)  # 1(urgent)..4(low)
    assignee: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    hunt_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("hunts.id"), nullable=True
    )
    owner_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=True
    )
    mitre_techniques: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    iocs: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # [{type, value, description}]
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # relationships
    tasks: Mapped[list["CaseTask"]] = relationship(
        back_populates="case", lazy="selectin", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_cases_hunt", "hunt_id"),
        Index("ix_cases_status", "status"),
    )


class CaseTask(Base):
    """Task within a case (Kanban board item)."""
    __tablename__ = "case_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    case_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="todo")  # todo|in-progress|done
    assignee: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # relationships
    case: Mapped["Case"] = relationship(back_populates="tasks")

    __table_args__ = (
        Index("ix_case_tasks_case", "case_id"),
    )


# ── Activity Log ──────────────────────────────────────────────────────


class ActivityLog(Base):
    """Audit trail / activity log for cases and hunts."""
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)  # case|hunt|annotation
    entity_id: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)  # created|updated|status_changed|etc
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_activity_entity", "entity_type", "entity_id"),
    )


# ── Alerts ────────────────────────────────────────────────────────────


class Alert(Base):
    """Security alert generated by analyzers or rules."""
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(16), default="medium")  # critical|high|medium|low|info
    status: Mapped[str] = mapped_column(String(24), default="new")  # new|acknowledged|in-progress|resolved|false-positive
    analyzer: Mapped[str] = mapped_column(String(64), nullable=False)  # which analyzer produced it
    score: Mapped[float] = mapped_column(Float, default=0.0)
    evidence: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # [{row_index, field, value, ...}]
    mitre_technique: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    hunt_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("hunts.id"), nullable=True
    )
    dataset_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("datasets.id"), nullable=True
    )
    case_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("cases.id"), nullable=True
    )
    assignee: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("ix_alerts_severity", "severity"),
        Index("ix_alerts_status", "status"),
        Index("ix_alerts_hunt", "hunt_id"),
        Index("ix_alerts_dataset", "dataset_id"),
    )


class AlertRule(Base):
    """User-defined alert rule (triggers analyzers automatically on upload)."""
    __tablename__ = "alert_rules"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    analyzer: Mapped[str] = mapped_column(String(64), nullable=False)  # analyzer name
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # analyzer config overrides
    severity_override: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    hunt_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("hunts.id"), nullable=True
    )  # None = global
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("ix_alert_rules_analyzer", "analyzer"),
    )


# ── Notebooks ────────────────────────────────────────────────────────


class Notebook(Base):
    """Investigation notebook — cell-based document for analyst notes and queries."""
    __tablename__ = "notebooks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cells: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # [{id, cell_type, source, output, metadata}]
    hunt_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("hunts.id"), nullable=True
    )
    case_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("cases.id"), nullable=True
    )
    owner_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=True
    )
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("ix_notebooks_hunt", "hunt_id"),
    )


# ── Playbook Runs ────────────────────────────────────────────────────


class PlaybookRun(Base):
    """Record of a playbook execution (links a template to a hunt/case)."""
    __tablename__ = "playbook_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    playbook_name: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="in-progress")  # in-progress | completed | aborted
    current_step: Mapped[int] = mapped_column(Integer, default=1)
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    step_results: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # [{step, status, notes, completed_at}]
    hunt_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("hunts.id"), nullable=True
    )
    case_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("cases.id"), nullable=True
    )
    started_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_playbook_runs_hunt", "hunt_id"),
        Index("ix_playbook_runs_status", "status"),
    )
<<<<<<< HEAD
    anomaly_score: Mapped[float] = mapped_column(Float, default=0.0)
    distance_from_centroid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cluster_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_outlier: Mapped[bool] = mapped_column(Boolean, default=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# -- Persistent Processing Tasks (Phase 2) ---

class ProcessingTask(Base):
    __tablename__ = "processing_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    hunt_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("hunts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    dataset_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=True, index=True
    )
    job_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("ix_processing_tasks_hunt_stage", "hunt_id", "stage"),
        Index("ix_processing_tasks_dataset_stage", "dataset_id", "stage"),
    )


# -- Playbook / Investigation Templates (Feature 3) ---

class Playbook(Base):
    __tablename__ = "playbooks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=True
    )
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)
    hunt_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("hunts.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    steps: Mapped[list["PlaybookStep"]] = relationship(
        back_populates="playbook", lazy="selectin", cascade="all, delete-orphan",
        order_by="PlaybookStep.order_index",
    )


class PlaybookStep(Base):
    __tablename__ = "playbook_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    playbook_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("playbooks.id", ondelete="CASCADE"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    step_type: Mapped[str] = mapped_column(String(32), default="manual")
    target_route: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    playbook: Mapped["Playbook"] = relationship(back_populates="steps")

    __table_args__ = (
        Index("ix_playbook_steps_playbook", "playbook_id"),
    )


# -- Saved Searches (Feature 5) ---

class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    search_type: Mapped[str] = mapped_column(String(32), nullable=False)
    query_params: Mapped[dict] = mapped_column(JSON, nullable=False)
    threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=True
    )
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_result_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_saved_searches_type", "search_type"),
    )
=======
>>>>>>> 7c454036c7ef6a3d6517f98cbee643fd0238e0b2
