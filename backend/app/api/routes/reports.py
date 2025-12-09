from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_active_user, get_tenant_id
from app.models.user import User
from app.models.report_template import ReportTemplate, Report
from app.schemas.report import ReportTemplateCreate, ReportTemplateRead, ReportCreate, ReportRead

router = APIRouter()


@router.get("/templates", response_model=List[ReportTemplateRead])
async def list_report_templates(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """List report templates scoped to tenant"""
    templates = db.query(ReportTemplate).filter(
        ReportTemplate.tenant_id == tenant_id
    ).offset(skip).limit(limit).all()
    return templates


@router.post("/templates", response_model=ReportTemplateRead, status_code=status.HTTP_201_CREATED)
async def create_report_template(
    template_data: ReportTemplateCreate,
    current_user: User = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """Create a new report template"""
    template = ReportTemplate(
        tenant_id=tenant_id,
        created_by=current_user.id,
        **template_data.dict()
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.post("/generate", response_model=ReportRead, status_code=status.HTTP_201_CREATED)
async def generate_report(
    report_data: ReportCreate,
    current_user: User = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Generate a new report
    
    This is a simplified implementation. In production, this would:
    1. Fetch relevant data based on report type
    2. Apply template formatting
    3. Generate PDF/HTML output
    4. Store file and return path
    """
    report = Report(
        tenant_id=tenant_id,
        template_id=report_data.template_id,
        title=report_data.title,
        report_type=report_data.report_type,
        format=report_data.format,
        status="generating",
        generated_by=current_user.id
    )
    db.add(report)
    db.commit()
    
    # Simulate report generation
    # In production, this would be an async task
    report.status = "completed"
    report.file_path = f"/reports/{report.id}.{report_data.format}"
    db.commit()
    db.refresh(report)
    
    return report


@router.get("/", response_model=List[ReportRead])
async def list_reports(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """List generated reports"""
    reports = db.query(Report).filter(
        Report.tenant_id == tenant_id
    ).order_by(Report.generated_at.desc()).offset(skip).limit(limit).all()
    return reports


@router.get("/{report_id}", response_model=ReportRead)
async def get_report(
    report_id: int,
    current_user: User = Depends(get_current_active_user),
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """Get a specific report"""
    report = db.query(Report).filter(
        Report.id == report_id,
        Report.tenant_id == tenant_id
    ).first()
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    return report
