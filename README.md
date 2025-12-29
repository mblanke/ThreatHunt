# ThreatHunt - Analyst-Assist Threat Hunting Platform

A modern threat hunting platform with integrated analyst-assist agent guidance. Analyze CSV artifact data exported from Velociraptor with AI-powered suggestions for investigation directions, analytical pivots, and hypothesis formation.

## Overview

ThreatHunt is a web application designed to help security analysts efficiently hunt for threats by:
- Importing CSV artifacts from Velociraptor or other sources
- Displaying data in an organized, queryable interface
- Providing AI-powered guidance through an analyst-assist agent
- Suggesting analytical directions, filters, and pivots
- Highlighting anomalies and patterns of interest

> **Agent Policy**: The analyst-assist agent provides read-only guidance only. It does not execute actions, escalate alerts, or modify data. All decisions remain with the analyst.

## Quick Start

### Docker (Recommended)

```bash
# Clone and navigate
git clone https://github.com/mblanke/ThreatHunt.git
cd ThreatHunt

# Configure provider (choose one)
cp .env.example .env
# Edit .env and set your LLM provider:
# Option 1: Online (OpenAI, etc.)
#   THREAT_HUNT_AGENT_PROVIDER=online
#   THREAT_HUNT_ONLINE_API_KEY=sk-your-key
# Option 2: Local (Ollama, GGML, etc.)
#   THREAT_HUNT_AGENT_PROVIDER=local
#   THREAT_HUNT_LOCAL_MODEL_PATH=/path/to/model
# Option 3: Networked (Internal inference service)
#   THREAT_HUNT_AGENT_PROVIDER=networked
#   THREAT_HUNT_NETWORKED_ENDPOINT=http://service:5000

# Start services
docker-compose up -d

# Verify
curl http://localhost:8000/api/agent/health
curl http://localhost:3000
```

Access at http://localhost:3000

### Local Development

**Backend**:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure provider
export THREAT_HUNT_ONLINE_API_KEY=sk-your-key
# OR set another provider env var

# Run
python run.py
# API at http://localhost:8000/docs
```

**Frontend** (new terminal):
```bash
cd frontend
npm install
npm start
# App at http://localhost:3000
```

## Features

### Analyst-Assist Agent 🤖
- **Read-only guidance**: Explains data patterns and suggests investigation directions
- **Context-aware**: Understands current dataset, host, and artifact type
- **Pluggable providers**: Local, networked, or online LLM backends
- **Transparent reasoning**: Explains logic with caveats and confidence scores
- **Governance-compliant**: Strictly adheres to agent policy (no execution, no escalation)

### Chat Interface
- Analyst asks questions about artifact data
- Agent provides guidance with suggested pivots and filters
- Conversation history for context continuity
- Real-time typing and response indicators

### Data Management
- Import CSV artifacts from Velociraptor
- Browse and filter findings by severity, host, artifact type
- Annotate findings with analyst notes
- Track investigation progress

## Architecture

### Backend
- **Framework**: FastAPI (Python 3.11)
- **Agent Module**: Pluggable LLM provider interface
- **API**: RESTful endpoints with OpenAPI documentation
- **Structure**: Modular design with clear separation of concerns

### Frontend
- **Framework**: React 18 with TypeScript
- **Components**: Agent chat panel + analysis dashboard
- **Styling**: CSS with responsive design
- **State Management**: React hooks + Context API

### LLM Providers
Supports three provider architectures:

1. **Local**: On-device or on-prem models (GGML, Ollama, vLLM)
2. **Networked**: Shared internal inference services
3. **Online**: External hosted APIs (OpenAI, Anthropic, Google)

Auto-detection: Automatically uses the first available provider.

## Project Structure

```
ThreatHunt/
├── backend/
│   ├── app/
│   │   ├── agents/              # Analyst-assist agent
│   │   │   ├── core.py          # ThreatHuntAgent class
│   │   │   ├── providers.py     # LLM provider interface
│   │   │   ├── config.py        # Configuration
│   │   │   └── __init__.py
│   │   ├── api/routes/          # API endpoints
│   │   │   ├── agent.py         # /api/agent/* routes
│   │   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app
│   │   └── __init__.py
│   ├── requirements.txt
│   ├── run.py
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── AgentPanel.tsx   # Chat interface
│   │   │   └── AgentPanel.css
│   │   ├── utils/
│   │   │   └── agentApi.ts      # API communication
│   │   ├── App.tsx
│   │   ├── App.css
│   │   ├── index.tsx
│   │   └── index.css
│   ├── public/index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── AGENT_IMPLEMENTATION.md       # Technical guide
├── INTEGRATION_GUIDE.md           # Deployment guide
├── IMPLEMENTATION_SUMMARY.md      # Overview
├── README.md                      # This file
├── ROADMAP.md
└── THREATHUNT_INTENT.md
```

## API Endpoints

### Agent Assistance
- **POST /api/agent/assist** - Request guidance on artifact data
- **GET /api/agent/health** - Check agent availability

See full API documentation at http://localhost:8000/docs

## Configuration

### LLM Provider Selection

Set via `THREAT_HUNT_AGENT_PROVIDER` environment variable:

```bash
# Auto-detect (tries local → networked → online)
THREAT_HUNT_AGENT_PROVIDER=auto

# Local (on-device/on-prem)
THREAT_HUNT_AGENT_PROVIDER=local
THREAT_HUNT_LOCAL_MODEL_PATH=/models/model.gguf

# Networked (internal service)
THREAT_HUNT_AGENT_PROVIDER=networked
THREAT_HUNT_NETWORKED_ENDPOINT=http://inference:5000
THREAT_HUNT_NETWORKED_KEY=api-key

# Online (hosted API)
THREAT_HUNT_AGENT_PROVIDER=online
THREAT_HUNT_ONLINE_API_KEY=sk-your-key
THREAT_HUNT_ONLINE_PROVIDER=openai
THREAT_HUNT_ONLINE_MODEL=gpt-3.5-turbo
```

### Agent Behavior

```bash
THREAT_HUNT_AGENT_MAX_TOKENS=1024
THREAT_HUNT_AGENT_REASONING=true
THREAT_HUNT_AGENT_HISTORY_LENGTH=10
THREAT_HUNT_AGENT_FILTER_SENSITIVE=true
```

See `.env.example` for all configuration options.

## Governance & Compliance

This implementation strictly follows governance principles:

- ✅ **Agents assist analysts** - No autonomous execution
- ✅ **No tool execution** - Agent provides guidance only
- ✅ **No alert escalation** - Analyst controls alerts
- ✅ **No data modification** - Read-only analysis
- ✅ **Transparent reasoning** - Explains guidance with caveats
- ✅ **Analyst authority** - All decisions remain with analyst

**References**:
- `goose-core/governance/AGENT_POLICY.md`
- `goose-core/governance/AI_RULES.md`
- `THREATHUNT_INTENT.md`

## Documentation

- **[AGENT_IMPLEMENTATION.md](AGENT_IMPLEMENTATION.md)** - Detailed technical architecture
- **[INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)** - Deployment and configuration
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Feature overview

## Testing the Agent

### Check Health
```bash
curl http://localhost:8000/api/agent/health
```

### Test API
```bash
curl -X POST http://localhost:8000/api/agent/assist \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What patterns suggest suspicious activity?",
    "dataset_name": "FileList",
    "artifact_type": "FileList",
    "host_identifier": "DESKTOP-ABC123"
  }'
```

### Use UI
1. Open http://localhost:3000
2. Enter a question in the agent panel
3. View guidance with suggested pivots and filters

## Troubleshooting

### Agent Unavailable (503)
- Check environment variables for provider configuration
- Verify LLM provider is accessible
- See logs: `docker-compose logs backend`

### No Frontend Response
- Verify backend health: `curl http://localhost:8000/api/agent/health`
- Check browser console for errors
- See logs: `docker-compose logs frontend`

See [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) for detailed troubleshooting.

## Development

### Running Tests
```bash
cd backend
pytest

cd ../frontend
npm test
```

### Building Images
```bash
docker-compose build
```

### Logs
```bash
docker-compose logs -f backend
docker-compose logs -f frontend
```

## Security Notes

For production deployment:
1. Add authentication to API endpoints
2. Enable HTTPS/TLS
3. Implement rate limiting
4. Filter sensitive data before LLM
5. Add audit logging
6. Use secrets management for API keys

See [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md#security-notes) for details.

## Future Enhancements

- [ ] Integration with actual CVE databases
- [ ] Fine-tuned models for cybersecurity domain
- [ ] Structured output from LLMs (JSON mode)
- [ ] Feedback loop on guidance quality
- [ ] Multi-modal support (images, documents)
- [ ] Compliance reporting and audit trails
- [ ] Performance optimization and caching

## Contributing

Follow the architecture and governance principles in `goose-core`. All changes must:
- Adhere to agent policy (read-only, advisory only)
- Conform to shared terminology in goose-core
- Include appropriate documentation
- Pass tests and lint checks

## License

See LICENSE file

## Support

For issues or questions:
1. Check [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)
2. Review [AGENT_IMPLEMENTATION.md](AGENT_IMPLEMENTATION.md)
3. See API docs at http://localhost:8000/docs
4. Check backend logs for errors

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- Node.js 18+ (for local development)

### Quick Start with Docker

1. Clone the repository:
```bash
git clone https://github.com/mblanke/ThreatHunt.git
cd ThreatHunt
```

2. Start all services:
```bash
docker-compose up -d
```

3. Access the application:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### Local Development

#### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your settings

# Run migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload
```

#### Frontend

```bash
cd frontend
npm install
npm start
```

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register a new user
- `POST /api/auth/login` - Login and receive JWT token
- `GET /api/auth/me` - Get current user profile
- `PUT /api/auth/me` - Update current user profile

### User Management (Admin only)
- `GET /api/users` - List all users in tenant
- `GET /api/users/{user_id}` - Get user by ID
- `PUT /api/users/{user_id}` - Update user
- `DELETE /api/users/{user_id}` - Deactivate user

### Tenants
- `GET /api/tenants` - List tenants
- `POST /api/tenants` - Create tenant (admin)
- `GET /api/tenants/{tenant_id}` - Get tenant by ID

### Hosts
- `GET /api/hosts` - List hosts (scoped to tenant)
- `POST /api/hosts` - Create host
- `GET /api/hosts/{host_id}` - Get host by ID

### Ingestion
- `POST /api/ingestion/ingest` - Upload and parse CSV files exported from Velociraptor

### VirusTotal
- `POST /api/vt/lookup` - Lookup hash in VirusTotal

## Authentication Flow

1. User registers or logs in via `/api/auth/login`
2. Backend returns JWT token with user_id, tenant_id, and role
3. Frontend stores token in localStorage
4. All subsequent API requests include token in Authorization header
5. Backend validates token and enforces tenant scoping

## Multi-Tenancy

- All data is scoped to tenant_id
- Users can only access data within their tenant
- Admin users have elevated permissions within their tenant
- Cross-tenant access requires explicit permissions

## Database Migrations

Create a new migration:
```bash
cd backend
alembic revision --autogenerate -m "Description of changes"
```

Apply migrations:
```bash
alembic upgrade head
```

Rollback migrations:
```bash
alembic downgrade -1
```

## Environment Variables

### Backend
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - Secret key for JWT signing (min 32 characters)
- `ACCESS_TOKEN_EXPIRE_MINUTES` - JWT token expiration time (default: 30)
- `VT_API_KEY` - VirusTotal API key for hash lookups

### Frontend
- `REACT_APP_API_URL` - Backend API URL (default: http://localhost:8000)

## Security

- Passwords are hashed using bcrypt
- JWT tokens include expiration time
- All API endpoints (except login/register) require authentication
- Role-based access control for admin operations
- Data isolation through tenant scoping

## Testing

### Backend
```bash
cd backend
pytest
```

### Frontend
```bash
cd frontend
npm test
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

[Your License Here]

## Support

For issues and questions, please open an issue on GitHub.
