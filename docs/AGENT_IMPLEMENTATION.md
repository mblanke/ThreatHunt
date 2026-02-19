# ThreatHunt Analyst-Assist Agent Implementation

## Overview

This implementation adds an analyst-assist agent to ThreatHunt that provides read-only guidance on CSV artifact data, analytical pivots, and hypotheses. The agent strictly adheres to the governance principles defined in `goose-core/governance/AGENT_POLICY.md`.

## Architecture

### Backend Stack
- **Framework**: FastAPI (Python 3.11)
- **Agent Module**: `backend/app/agents/`
  - `core.py`: ThreatHuntAgent class with guidance logic
  - `providers.py`: Pluggable LLM provider interface
  - `config.py`: Configuration management

### Frontend Stack
- **Framework**: React with TypeScript
- **Components**: AgentPanel chat interface
- **Styling**: CSS with responsive design

### API Endpoint
- **POST /api/agent/assist**: Request analyst guidance
- **GET /api/agent/health**: Check agent availability

## LLM Provider Architecture

The agent supports three provider types, selectable via configuration:

### 1. Local Provider
**Use Case**: On-device or on-premise models

Environment variables:
```bash
THREAT_HUNT_AGENT_PROVIDER=local
THREAT_HUNT_LOCAL_MODEL_PATH=/path/to/model.gguf
```

Supported frameworks:
- llama-cpp-python (GGML models)
- Ollama API
- vLLM
- Other local inference engines

### 2. Networked Provider
**Use Case**: Shared internal inference services

Environment variables:
```bash
THREAT_HUNT_AGENT_PROVIDER=networked
THREAT_HUNT_NETWORKED_ENDPOINT=http://inference-service:5000
THREAT_HUNT_NETWORKED_KEY=api-key-here
```

Supported architectures:
- Internal inference service API
- LLM inference container clusters
- Enterprise inference gateways

### 3. Online Provider
**Use Case**: External hosted APIs

Environment variables:
```bash
THREAT_HUNT_AGENT_PROVIDER=online
THREAT_HUNT_ONLINE_API_KEY=sk-your-api-key
THREAT_HUNT_ONLINE_PROVIDER=openai
THREAT_HUNT_ONLINE_MODEL=gpt-3.5-turbo
```

Supported providers:
- OpenAI (GPT-3.5, GPT-4)
- Anthropic Claude
- Google Gemini
- Other hosted LLM services

### Auto Provider Selection
Set `THREAT_HUNT_AGENT_PROVIDER=auto` to automatically use the first available provider:
1. Local (if model path exists)
2. Networked (if endpoint is configured)
3. Online (if API key is set)

## Backend Implementation

### Agent Request/Response Flow

**Request** (AgentContext):
```python
{
    "query": "What patterns suggest suspicious file modifications?",
    "dataset_name": "FileList-2025-12-26",
    "artifact_type": "FileList",
    "host_identifier": "DESKTOP-ABC123",
    "data_summary": "File listing from system scan",
    "conversation_history": [...]
}
```

**Response** (AgentResponse):
```python
{
    "guidance": "Based on the files listed, ...",
    "confidence": 0.8,
    "suggested_pivots": ["Analyze temporal patterns", "Cross-reference with IOCs"],
    "suggested_filters": ["Filter by modification time", "Sort by file size"],
    "caveats": "Guidance is based on available data context...",
    "reasoning": "Analysis generated based on patterns..."
}
```

### Governance Enforcement

The agent is designed with hard constraints to ensure compliance:

1. **Read-Only**: Agent accepts context data but cannot:
   - Execute tools or actions
   - Modify database or schema
   - Escalate findings to alerts
   - Access external systems

2. **Advisory Only**: All guidance is clearly marked as:
   - Suggestions, not directives
   - Confidence-rated
   - Accompanied by caveats
   - Attributed to the agent

3. **Analyst Control**: The UI emphasizes:
   - Agent provides guidance only
   - Analysts retain all decision-making authority
   - All next steps require analyst action

## Frontend Implementation

### AgentPanel Component

Located in `frontend/src/components/AgentPanel.tsx`:

**Features**:
- Chat-style interface for analyst questions
- Context display showing current dataset/host/artifact
- Rich response formatting with:
  - Main guidance text
  - Suggested analytical pivots (clickable)
  - Suggested data filters
  - Confidence scores
  - Caveats and assumptions
  - Reasoning explanation
- Conversation history for context
- Responsive design (desktop and mobile)
- Loading states and error handling

**Props**:
```typescript
interface AgentPanelProps {
  dataset_name?: string;
  artifact_type?: string;
  host_identifier?: string;
  data_summary?: string;
  onAnalysisAction?: (action: string) => void;
}
```

### Integration in Main UI

The agent panel is integrated into the main ThreatHunt dashboard as a sidebar component. In `App.tsx`:

1. Main analysis view occupies left side
2. Agent panel occupies right sidebar
3. Context automatically updated when analyst switches datasets/hosts
4. Responsive layout: stacks vertically on mobile

## Configuration

### Environment Variables

```bash
# Provider selection
THREAT_HUNT_AGENT_PROVIDER=auto              # auto, local, networked, or online

# Local provider
THREAT_HUNT_LOCAL_MODEL_PATH=/models/model.gguf

# Networked provider
THREAT_HUNT_NETWORKED_ENDPOINT=http://service:5000
THREAT_HUNT_NETWORKED_KEY=api-key

# Online provider
THREAT_HUNT_ONLINE_API_KEY=sk-key
THREAT_HUNT_ONLINE_PROVIDER=openai
THREAT_HUNT_ONLINE_MODEL=gpt-3.5-turbo

# Agent behavior
THREAT_HUNT_AGENT_MAX_TOKENS=1024
THREAT_HUNT_AGENT_REASONING=true
THREAT_HUNT_AGENT_HISTORY_LENGTH=10
THREAT_HUNT_AGENT_FILTER_SENSITIVE=true

# Frontend
REACT_APP_API_URL=http://localhost:8000
```

### Docker Deployment

Use `docker-compose.yml` for full stack deployment:

```bash
# Build and start services
docker-compose up -d

# Verify health
curl http://localhost:8000/api/agent/health
curl http://localhost:3000

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Stop services
docker-compose down
```

## Security Considerations

1. **API Access**: Backend should be protected with authentication in production
2. **LLM Privacy**: Sensitive data (IPs, usernames) should be filtered before sending to online providers
3. **Error Messages**: Production should use generic error messages, not expose internal details
4. **Rate Limiting**: Implement rate limiting on agent endpoints
5. **Conversation History**: Consider data retention policies for conversation logs

## Testing

### Manual Testing

1. **Agent Health**:
   ```bash
   curl http://localhost:8000/api/agent/health
   ```

2. **Agent Assistance** (without frontend):
   ```bash
   curl -X POST http://localhost:8000/api/agent/assist \
     -H "Content-Type: application/json" \
     -d '{
       "query": "What suspicious patterns do you see?",
       "dataset_name": "FileList",
       "artifact_type": "FileList",
       "host_identifier": "HOST123"
     }'
   ```

3. **Frontend UI**:
   - Navigate to http://localhost:3000
   - Type question in agent panel
   - Verify response displays correctly

## Future Enhancements

1. **Structured Output**: Use LLM JSON mode or function calling for more reliable parsing
2. **Context Filtering**: Automatically filter sensitive data before sending to LLM
3. **Multi-Modal**: Support image uploads (binary analysis, network diagrams)
4. **Caching**: Cache common agent responses to reduce latency
5. **Feedback Loop**: Capture analyst feedback on guidance quality
6. **Integration**: Connect agent to actual CVE databases, threat feeds
7. **Custom Models**: Support fine-tuned models for threat hunting domain
8. **Audit Trail**: Comprehensive logging of all agent interactions

## Governance Compliance

This implementation strictly follows:
- `goose-core/governance/AGENT_POLICY.md` - Agent boundaries and allowed functions
- `goose-core/governance/AI_RULES.md` - AI system rules
- `goose-core/governance/SCOPE.md` - Shared vs application-specific responsibility
- `ThreatHunt/THREATHUNT_INTENT.md` - Agent role in threat hunting

**Key Principles**:
- ✅ Agents assist analysts, never act autonomously
- ✅ No execution without explicit analyst approval
- ✅ No database or schema changes
- ✅ No alert escalation
- ✅ Read-only guidance
- ✅ Transparent reasoning and caveats
- ✅ Analyst retains all authority

## Troubleshooting

### Agent Unavailable (503)
- Check environment variables for provider configuration
- Verify LLM provider is accessible
- Review backend logs: `docker-compose logs backend`

### Slow Responses
- Check LLM provider latency
- Reduce MAX_TOKENS if appropriate
- Consider local provider for latency-sensitive deployments

### No Responses from Frontend
- Verify backend health: `curl http://localhost:8000/api/agent/health`
- Check browser console for errors
- Verify REACT_APP_API_URL in frontend environment
- Check CORS configuration if frontend hosted separately

## File Structure

```
ThreatHunt/
├── backend/
│   ├── app/
│   │   ├── agents/              # Agent module
│   │   │   ├── __init__.py
│   │   │   ├── core.py          # ThreatHuntAgent class
│   │   │   ├── providers.py     # LLM provider interface
│   │   │   └── config.py        # Agent configuration
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── __init__.py
│   │   │   │   └── agent.py     # /api/agent/* endpoints
│   │   ├── __init__.py
│   │   └── main.py              # FastAPI app
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── AgentPanel.tsx   # Agent chat component
│   │   │   └── AgentPanel.css
│   │   ├── utils/
│   │   │   └── agentApi.ts      # API communication
│   │   ├── App.tsx              # Main app with agent
│   │   ├── App.css
│   │   ├── index.tsx
│   ├── public/
│   │   └── index.html
│   ├── package.json
│   └── tsconfig.json
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
├── .env.example
├── AGENT_IMPLEMENTATION.md       # This file
├── README.md
└── THREATHUNT_INTENT.md
```

