# ThreatHunt Analyst-Assist Agent - Integration Guide

## Quick Reference

### Files Created

**Backend (10 files)**
- `backend/app/agents/core.py` - ThreatHuntAgent class
- `backend/app/agents/providers.py` - LLM provider interface
- `backend/app/agents/config.py` - Agent configuration
- `backend/app/agents/__init__.py` - Module initialization
- `backend/app/api/routes/agent.py` - /api/agent/* endpoints
- `backend/app/api/__init__.py` - API module init
- `backend/app/main.py` - FastAPI application
- `backend/app/__init__.py` - App module init
- `backend/requirements.txt` - Python dependencies
- `backend/run.py` - Development server entry point

**Frontend (7 files)**
- `frontend/src/components/AgentPanel.tsx` - React chat component
- `frontend/src/components/AgentPanel.css` - Component styles
- `frontend/src/utils/agentApi.ts` - API communication
- `frontend/src/App.tsx` - Main application with agent
- `frontend/src/App.css` - Application styles
- `frontend/src/index.tsx` - React entry point
- `frontend/public/index.html` - HTML template
- `frontend/package.json` - npm dependencies
- `frontend/tsconfig.json` - TypeScript config

**Docker & Config (5 files)**
- `Dockerfile.backend` - Backend container
- `Dockerfile.frontend` - Frontend container
- `docker-compose.yml` - Full stack orchestration
- `.env.example` - Configuration template
- `.gitignore` - Version control exclusions

**Documentation (3 files)**
- `AGENT_IMPLEMENTATION.md` - Detailed technical guide
- `IMPLEMENTATION_SUMMARY.md` - High-level overview
- `INTEGRATION_GUIDE.md` - This file

### Provider Configuration Quick Start

**Option 1: Online (OpenAI) - Easiest**
```bash
cp .env.example .env
# Edit .env:
THREAT_HUNT_AGENT_PROVIDER=online
THREAT_HUNT_ONLINE_API_KEY=sk-your-openai-key
THREAT_HUNT_ONLINE_MODEL=gpt-3.5-turbo

docker-compose up -d
# Access at http://localhost:3000
```

**Option 2: Local Model (Ollama) - Best for Privacy**
```bash
# Install Ollama and pull model
ollama pull mistral  # or llama2, neural-chat, etc.

cp .env.example .env
# Edit .env:
THREAT_HUNT_AGENT_PROVIDER=local
THREAT_HUNT_LOCAL_MODEL_PATH=/path/to/model

# Update docker-compose.yml to connect to Ollama
# Add to backend service:
# extra_hosts:
#   - "host.docker.internal:host-gateway"
# THREAT_HUNT_AGENT_PROVIDER=local
# THREAT_HUNT_LOCAL_MODEL_PATH=~/.ollama/models/

docker-compose up -d
```

**Option 3: Internal Service - Enterprise**
```bash
cp .env.example .env
# Edit .env:
THREAT_HUNT_AGENT_PROVIDER=networked
THREAT_HUNT_NETWORKED_ENDPOINT=http://your-inference-service:5000
THREAT_HUNT_NETWORKED_KEY=your-api-key

docker-compose up -d
```

## Installation Steps

### Prerequisites
- Docker & Docker Compose (recommended)
- OR Python 3.11 + Node.js 18 (local development)

### Method 1: Docker (Recommended)

```bash
cd /path/to/ThreatHunt

# 1. Configure provider
cp .env.example .env
# Edit .env and set your LLM provider

# 2. Build and start
docker-compose up -d

# 3. Verify
curl http://localhost:8000/api/agent/health
curl http://localhost:3000

# 4. Access UI
open http://localhost:3000
```

### Method 2: Local Development

**Backend**:
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Set provider (choose one)
export THREAT_HUNT_ONLINE_API_KEY=sk-your-key
# OR
export THREAT_HUNT_LOCAL_MODEL_PATH=/path/to/model
# OR
export THREAT_HUNT_NETWORKED_ENDPOINT=http://service:5000

# Run server
python run.py
# API at http://localhost:8000/docs
```

**Frontend** (new terminal):
```bash
cd frontend

# Install dependencies
npm install

# Start dev server
REACT_APP_API_URL=http://localhost:8000 npm start
# App at http://localhost:3000
```

## Testing the Agent

### 1. Check Agent Health
```bash
curl http://localhost:8000/api/agent/health

# Expected response (if configured):
{
  "status": "healthy",
  "provider": "OnlineProvider",
  "max_tokens": 1024,
  "reasoning_enabled": true
}
```

### 2. Test API Directly
```bash
curl -X POST http://localhost:8000/api/agent/assist \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What file modifications are suspicious?",
    "dataset_name": "FileList",
    "artifact_type": "FileList",
    "host_identifier": "DESKTOP-TEST",
    "data_summary": "System file listing from scan"
  }'
```

### 3. Test UI
1. Open http://localhost:3000
2. See sample data table
3. Click "Ask" button at bottom right
4. Type a question in the agent panel
5. Verify response appears with suggestions

## Deployment Checklist

- [ ] Configure LLM provider (env vars)
- [ ] Test agent health endpoint
- [ ] Test API with sample request
- [ ] Test frontend UI
- [ ] Configure CORS if frontend on different domain
- [ ] Add authentication (JWT/OAuth) for production
- [ ] Set up logging/monitoring
- [ ] Create backups of configuration
- [ ] Document provider credentials management
- [ ] Set up auto-scaling (if needed)

## Monitoring & Troubleshooting

### Check Logs
```bash
# Backend logs
docker-compose logs -f backend

# Frontend logs
docker-compose logs -f frontend

# Specific error
docker-compose logs backend | grep -i error
```

### Common Issues

**503 - Agent Unavailable**
```
Cause: No LLM provider configured
Fix: Set THREAT_HUNT_ONLINE_API_KEY or other provider env var
```

**CORS Error in Browser Console**
```
Cause: Frontend and backend on different origins
Fix: Update REACT_APP_API_URL or add frontend domain to CORS
```

**Slow Responses**
```
Cause: LLM provider latency (especially online)
Options:
  1. Use local provider instead
  2. Reduce MAX_TOKENS
  3. Check network connectivity
```

**Provider Not Found**
```
Cause: Model path or endpoint doesn't exist
Fix: Verify path/endpoint in .env
     docker-compose exec backend python -c "from app.agents import get_provider; get_provider()"
```

## API Reference

### POST /api/agent/assist

Request guidance on artifact data.

**Request Body**:
```typescript
{
  query: string;                    // Analyst question
  dataset_name?: string;            // CSV dataset name
  artifact_type?: string;           // Artifact type
  host_identifier?: string;         // Host/IP identifier
  data_summary?: string;            // Context description
  conversation_history?: Array<{    // Previous messages
    role: string;
    content: string;
  }>;
}
```

**Response**:
```typescript
{
  guidance: string;                     // Advisory text
  confidence: number;                   // 0.0 to 1.0
  suggested_pivots: string[];           // Analysis directions
  suggested_filters: string[];          // Data filters
  caveats?: string;                     // Limitations
  reasoning?: string;                   // Explanation
}
```

**Status Codes**:
- `200` - Success
- `400` - Bad request
- `503` - Service unavailable

### GET /api/agent/health

Check agent availability and configuration.

**Response**:
```typescript
{
  status: "healthy" | "unavailable" | "error";
  provider?: string;                    // Provider class name
  max_tokens?: number;                  // Max response length
  reasoning_enabled?: boolean;
  configured_providers?: {              // If unavailable
    local: boolean;
    networked: boolean;
    online: boolean;
  };
}
```

## Security Notes

### For Production

1. **Authentication**: Add JWT token validation to endpoints
   ```python
   from fastapi.security import HTTPBearer
   security = HTTPBearer()
   
   @router.post("/assist")
   async def assist(request: AssistRequest, credentials: HTTPAuthorizationCredentials = Depends(security)):
       # Verify token
   ```

2. **Rate Limiting**: Install and use `slowapi`
   ```python
   from slowapi import Limiter
   limiter = Limiter(key_func=get_remote_address)
   
   @limiter.limit("10/minute")
   async def assist(request: AssistRequest):
   ```

3. **HTTPS**: Use reverse proxy (nginx) with TLS

4. **Data Filtering**: Filter sensitive data before LLM
   ```python
   # Remove IPs, usernames, hashes
   filtered = filter_sensitive(request.data_summary)
   ```

5. **Audit Logging**: Log all agent requests
   ```python
   logger.info(f"Agent: user={user_id} query={query} host={host}")
   ```

## Configuration Reference

**Agent Settings**:
```bash
THREAT_HUNT_AGENT_PROVIDER          # auto, local, networked, online
THREAT_HUNT_AGENT_MAX_TOKENS        # Default: 1024
THREAT_HUNT_AGENT_REASONING         # Default: true
THREAT_HUNT_AGENT_HISTORY_LENGTH    # Default: 10
THREAT_HUNT_AGENT_FILTER_SENSITIVE  # Default: true
```

**Provider: Local**:
```bash
THREAT_HUNT_LOCAL_MODEL_PATH        # Path to .gguf or other model
```

**Provider: Networked**:
```bash
THREAT_HUNT_NETWORKED_ENDPOINT      # http://service:5000
THREAT_HUNT_NETWORKED_KEY           # API key for service
```

**Provider: Online**:
```bash
THREAT_HUNT_ONLINE_API_KEY          # Provider API key
THREAT_HUNT_ONLINE_PROVIDER         # openai, anthropic, google, etc
THREAT_HUNT_ONLINE_MODEL            # Model name (gpt-3.5-turbo, etc)
```

## Architecture Decisions

### Why Pluggable Providers?
- Deployment flexibility (cloud, on-prem, hybrid)
- Privacy control (local vs online)
- Cost optimization
- Vendor lock-in prevention

### Why Conversation History?
- Better context for follow-up questions
- Maintains thread of investigation
- Reduces redundant explanations

### Why Read-Only?
- Safety: Agent cannot accidentally modify data
- Compliance: Adheres to governance requirements
- Trust: Humans retain control

### Why Config-Based?
- No code changes for provider switching
- Easy environment-specific configuration
- CI/CD friendly

## Next Steps

1. **Configure Provider**: Set env vars for your chosen LLM
2. **Deploy**: Use docker-compose or local development
3. **Test**: Verify health endpoint and sample request
4. **Integrate**: Add to your threat hunting workflow
5. **Monitor**: Track agent usage and quality
6. **Iterate**: Gather analyst feedback and improve

## Support & Troubleshooting

See `AGENT_IMPLEMENTATION.md` for detailed troubleshooting.

Key support files:
- Backend logs: `docker-compose logs backend`
- Frontend console: Browser DevTools
- Health check: `curl http://localhost:8000/api/agent/health`
- API docs: http://localhost:8000/docs (when running)

## References

- **Governance**: See `goose-core/governance/AGENT_POLICY.md`
- **Intent**: See `THREATHUNT_INTENT.md`
- **Technical**: See `AGENT_IMPLEMENTATION.md`
- **FastAPI**: https://fastapi.tiangolo.com
- **React**: https://react.dev
- **Docker**: https://docs.docker.com

