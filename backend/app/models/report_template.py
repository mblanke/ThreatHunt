from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.core.database import Base


class ReportTemplate(Base):
    __tablename__ = "report_templates"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    template_type = Column(String, nullable=False)  # case_summary, host_analysis, threat_report
    template_config = Column(JSON, nullable=False)  # Configuration for report generation
    is_default = Column(Boolean, default=False, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant")
    creator = relationship("User")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("report_templates.id"), nullable=True)
    title = Column(String, nullable=False)
    report_type = Column(String, nullable=False)
    format = Column(String, nullable=False)  # pdf, html, json
    file_path = Column(String, nullable=True)
    status = Column(String, nullable=False)  # generating, completed, failed
    generated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    tenant = relationship("Tenant")
    template = relationship("ReportTemplate")
    generator = relationship("User")
