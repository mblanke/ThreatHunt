# Velo Threat Hunter

A modern web application for threat hunting and security analysis, built with React frontend and Flask backend.

## Features

- **Security Tools Detection**: Identify running security tools (AV, EDR, VPN)
- **CSV Processing**: Upload and analyze security logs
- **Baseline Analysis**: System baseline comparison
- **Network Analysis**: Network traffic and connection analysis
- **VirusTotal Integration**: File and URL reputation checking

## Architecture

```
ThreatHunt/
├── frontend/          # React application
├── backend/           # Flask API server
├── uploaded/          # File upload storage
└── output/           # Analysis results
```

## Quick Start

### Backend Setup

```bash
cd backend
chmod +x setup_backend.sh
./setup_backend.sh
source venv/bin/activate
python app.py
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

- `GET /` - Serve React app
- `GET /api/health` - Health check
- `POST /api/upload` - File upload
- `GET /api/analysis/<id>` - Get analysis results

## Security Considerations

- File upload validation
- Input sanitization
- Rate limiting
- CORS configuration

## Contributing

1. Fork the repository
2. Create feature branch
3. Submit pull request

## License

MIT License
