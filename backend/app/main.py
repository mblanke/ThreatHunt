"""ThreatHunt backend application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import agent

# Create FastAPI application
app = FastAPI(
    title="ThreatHunt API",
    description="Analyst-assist threat hunting platform with agent guidance",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to known domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(agent.router)


@app.get("/", tags=["health"])
async def root():
    """API health check."""
    return {
        "service": "ThreatHunt API",
        "status": "running",
        "docs": "/docs",
    }
