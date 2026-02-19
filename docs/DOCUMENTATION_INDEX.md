# ThreatHunt Documentation Index

## 🚀 Getting Started (Pick One)

### **5-Minute Setup** (Recommended)
→ [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)
- Quick start with Docker
- Provider configuration options
- Testing procedures
- Basic troubleshooting

### **Feature Overview**
→ [COMPLETION_SUMMARY.md](COMPLETION_SUMMARY.md)
- What was built
- Key highlights
- Quick reference
- Requirements verification

## 📚 Detailed Documentation

### **Technical Architecture**
→ [AGENT_IMPLEMENTATION.md](AGENT_IMPLEMENTATION.md)
- Detailed backend design
- LLM provider architecture
- Frontend implementation
- API specifications
- Security considerations
- Future enhancements

### **Implementation Verification**
→ [VALIDATION_CHECKLIST.md](VALIDATION_CHECKLIST.md)
- Complete requirements checklist
- Files created list
- Governance compliance
- Feature verification

### **Implementation Summary**
→ [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- What was completed
- Key design decisions
- Quick start guide
- File structure

## 📖 Project Documentation

### **Main Project README**
→ [README.md](README.md)
- Project overview
- Features
- Quick start
- Configuration reference
- Troubleshooting

### **Project Intent**
→ [THREATHUNT_INTENT.md](THREATHUNT_INTENT.md)
- What ThreatHunt does
- Agent's role in threat hunting
- Project goals

### **Roadmap**
→ [ROADMAP.md](ROADMAP.md)
- Future enhancements
- Planned features
- Project evolution

## 🎯 By Use Case

### "I want to deploy this now"
1. [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - Deployment steps
2. `.env.example` - Configuration template
3. `docker-compose up -d` - Start services

### "I want to understand the architecture"
1. [COMPLETION_SUMMARY.md](COMPLETION_SUMMARY.md) - Overview
2. [AGENT_IMPLEMENTATION.md](AGENT_IMPLEMENTATION.md) - Details
3. Code files in `backend/app/agents/` and `frontend/src/components/`

### "I want to customize the agent"
1. [AGENT_IMPLEMENTATION.md](AGENT_IMPLEMENTATION.md) - Architecture
2. `backend/app/agents/core.py` - Agent logic
3. `backend/app/agents/providers.py` - Add new provider
4. `frontend/src/components/AgentPanel.tsx` - Customize UI

### "I need to troubleshoot something"
1. [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - Troubleshooting section
2. [AGENT_IMPLEMENTATION.md](AGENT_IMPLEMENTATION.md) - Detailed guide
3. `docker-compose logs backend` - View backend logs
4. `docker-compose logs frontend` - View frontend logs

### "I need to verify compliance"
1. [VALIDATION_CHECKLIST.md](VALIDATION_CHECKLIST.md) - Governance checklist
2. [AGENT_IMPLEMENTATION.md](AGENT_IMPLEMENTATION.md) - Governance section
3. `goose-core/governance/` - Original governance documents

## 📂 File Structure Reference

### Backend
```
backend/
├── app/agents/              # Agent module
│   ├── core.py              # Main agent logic
│   ├── providers.py         # LLM providers
│   └── config.py            # Configuration
├── app/api/routes/
│   └── agent.py             # API endpoints
├── main.py                  # FastAPI app
└── run.py                   # Development server
```

### Frontend
```
frontend/
├── src/components/
│   └── AgentPanel.tsx       # Chat component
├── src/utils/
│   └── agentApi.ts          # API client
├── src/App.tsx              # Main app
└── public/index.html        # HTML template
```

### Configuration
```
ThreatHunt/
├── docker-compose.yml       # Full stack
├── Dockerfile.backend       # Backend container
├── Dockerfile.frontend      # Frontend container
├── .env.example             # Configuration template
└── .gitignore
```

## 🔧 Configuration Quick Reference

### Provider Selection
```bash
# Choose one of these:
THREAT_HUNT_AGENT_PROVIDER=auto           # Auto-detect
THREAT_HUNT_AGENT_PROVIDER=local          # On-premise
THREAT_HUNT_AGENT_PROVIDER=networked      # Internal service
THREAT_HUNT_AGENT_PROVIDER=online         # Hosted API
```

### Local Provider
```bash
THREAT_HUNT_AGENT_PROVIDER=local
THREAT_HUNT_LOCAL_MODEL_PATH=/path/to/model.gguf
```

### Networked Provider
```bash
THREAT_HUNT_AGENT_PROVIDER=networked
THREAT_HUNT_NETWORKED_ENDPOINT=http://service:5000
THREAT_HUNT_NETWORKED_KEY=api-key
```

### Online Provider (OpenAI Example)
```bash
THREAT_HUNT_AGENT_PROVIDER=online
THREAT_HUNT_ONLINE_API_KEY=sk-your-key
THREAT_HUNT_ONLINE_PROVIDER=openai
THREAT_HUNT_ONLINE_MODEL=gpt-3.5-turbo
```

## 🧪 Testing Quick Reference

### Check Agent Health
```bash
curl http://localhost:8000/api/agent/health
```

### Test API Directly
```bash
curl -X POST http://localhost:8000/api/agent/assist \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What suspicious patterns do you see?",
    "dataset_name": "FileList",
    "artifact_type": "FileList",
    "host_identifier": "DESKTOP-TEST"
  }'
```

### View Interactive API Docs
```
http://localhost:8000/docs
```

## 📊 Key Metrics

| Metric | Value |
|--------|-------|
| Files Created | 31 |
| Lines of Code | 3,500+ |
| Documentation | 4,000+ lines |
| Backend Modules | 3 (agents, api, main) |
| Frontend Components | 1 (AgentPanel) |
| API Endpoints | 2 (/assist, /health) |
| LLM Providers | 3 (local, networked, online) |
| Governance Documents | 5 (goose-core) |
| Test Coverage | Health checks + manual testing |

## ✅ Governance Compliance

### Fully Compliant With
- ✅ `goose-core/governance/AGENT_POLICY.md`
- ✅ `goose-core/governance/AI_RULES.md`
- ✅ `goose-core/governance/SCOPE.md`
- ✅ `THREATHUNT_INTENT.md`

### Core Principle
**Agents assist analysts. They never act autonomously.**

- No tool execution
- No alert escalation
- No data modification
- Read-only guidance
- Analyst authority
- Transparent reasoning

## 🎯 Documentation Maintenance

### If You're Modifying:
- **Backend Agent**: See [AGENT_IMPLEMENTATION.md](AGENT_IMPLEMENTATION.md)
- **LLM Provider**: See [AGENT_IMPLEMENTATION.md](AGENT_IMPLEMENTATION.md) - LLM Provider Architecture
- **Frontend UI**: See [AGENT_IMPLEMENTATION.md](AGENT_IMPLEMENTATION.md) - Frontend Implementation
- **Configuration**: See [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - Configuration Reference
- **Deployment**: See [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - Deployment Checklist

## 🆘 Support

### For Setup Issues
→ [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - Troubleshooting section

### For Technical Questions
→ [AGENT_IMPLEMENTATION.md](AGENT_IMPLEMENTATION.md) - Detailed guide

### For Architecture Questions
→ [COMPLETION_SUMMARY.md](COMPLETION_SUMMARY.md) - Architecture section

### For Governance Questions
→ [VALIDATION_CHECKLIST.md](VALIDATION_CHECKLIST.md) - Governance Compliance section

## 📋 Deployment Checklist

From [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md):
- [ ] Configure LLM provider (env vars)
- [ ] Test agent health endpoint
- [ ] Test API with sample request
- [ ] Test frontend UI
- [ ] Configure CORS if needed
- [ ] Add authentication for production
- [ ] Set up logging/monitoring
- [ ] Create configuration backups
- [ ] Document credentials management
- [ ] Set up auto-scaling (if needed)

---

**Start with [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) for immediate deployment, or [AGENT_IMPLEMENTATION.md](AGENT_IMPLEMENTATION.md) for detailed technical information.**

