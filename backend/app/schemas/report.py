from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class ReportTemplateBase(BaseModel):
    """Base report template schema"""
    name: str
    description: Optional[str] = None
    template_type: str
    template_config: Dict[str, Any]
    is_default: bool = False


class ReportTemplateCreate(ReportTemplateBase):
    """Schema for creating a report template"""
    pass


class ReportTemplateRead(ReportTemplateBase):
    """Schema for reading report template data"""
    id: int
    tenant_id: int
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True


class ReportBase(BaseModel):
    """Base report schema"""
    title: str
    report_type: str
    format: str


class ReportCreate(ReportBase):
    """Schema for creating a report"""
    template_id: Optional[int] = None


class ReportRead(ReportBase):
    """Schema for reading report data"""
    id: int
    tenant_id: int
    template_id: Optional[int]
    file_path: Optional[str]
    status: str
    generated_by: int
    generated_at: datetime

    class Config:
        from_attributes = True
