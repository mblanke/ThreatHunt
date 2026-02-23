from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/db/models.py')
t=p.read_text(encoding='utf-8')
if 'class ProcessingTask(Base):' in t:
    print('processing task model already exists')
    raise SystemExit(0)
insert='''

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
'''
# insert before Playbook section
marker='\n\n# -- Playbook / Investigation Templates (Feature 3) ---\n'
if marker not in t:
    raise SystemExit('marker not found for insertion')
t=t.replace(marker, insert+marker)
p.write_text(t,encoding='utf-8')
print('added ProcessingTask model')
