from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    auth, users, tenants, hosts, ingestion, vt, audit,
    notifications, velociraptor, playbooks, threat_intel, reports, llm
)
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    description="Multi-tenant threat hunting companion for Velociraptor with ML-powered threat detection and distributed LLM routing",
    version="1.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(tenants.router, prefix="/api/tenants", tags=["Tenants"])
app.include_router(hosts.router, prefix="/api/hosts", tags=["Hosts"])
app.include_router(ingestion.router, prefix="/api/ingestion", tags=["Ingestion"])
app.include_router(vt.router, prefix="/api/vt", tags=["VirusTotal"])
app.include_router(audit.router, prefix="/api/audit", tags=["Audit Logs"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(velociraptor.router, prefix="/api/velociraptor", tags=["Velociraptor"])
app.include_router(playbooks.router, prefix="/api/playbooks", tags=["Playbooks"])
app.include_router(threat_intel.router, prefix="/api/threat-intel", tags=["Threat Intelligence"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(llm.router, prefix="/api/llm", tags=["Distributed LLM"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": "1.1.0",
        "docs": "/docs",
        "features": [
            "JWT Authentication with 2FA",
            "Multi-tenant isolation",
            "Audit logging",
            "Real-time notifications",
            "Velociraptor integration",
            "ML-powered threat detection",
            "Automated playbooks",
            "Advanced reporting",
            "Distributed LLM routing (Phase 5)"
        ]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
