# Quick Start Guide

This guide will help you get VelociCompanion up and running in minutes.

## Prerequisites

- Docker and Docker Compose installed
- 8GB RAM minimum
- Ports 3000, 5432, and 8000 available

## Step 1: Start the Application

```bash
# Clone the repository
git clone https://github.com/mblanke/ThreatHunt.git
cd ThreatHunt

# Start all services
docker-compose up -d

# Check service status
docker-compose ps
```

Expected output:
```
NAME                COMMAND                  SERVICE             STATUS              PORTS
threathunt-backend-1   "sh -c 'alembic upgr…"   backend             running             0.0.0.0:8000->8000/tcp
threathunt-db-1        "docker-entrypoint.s…"   db                  running             0.0.0.0:5432->5432/tcp
threathunt-frontend-1  "docker-entrypoint.s…"   frontend            running             0.0.0.0:3000->3000/tcp
```

## Step 2: Verify Backend is Running

```bash
# Check backend health
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy"}

# View API documentation
open http://localhost:8000/docs
```

## Step 3: Access the Frontend

Open your browser and navigate to:
```
http://localhost:3000
```

You should see the VelociCompanion login page.

## Step 4: Create Your First User

### Option A: Via API (using curl)

```bash
# Register a new user
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123",
    "role": "admin"
  }'

# Login to get a token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"
```

### Option B: Via Frontend

1. The first time you access the app, you'll need to register via API first (as shown above)
2. Then login through the frontend at http://localhost:3000/login

## Step 5: Explore the API

Use the interactive API documentation at:
```
http://localhost:8000/docs
```

Click "Authorize" and enter your token in the format:
```
Bearer YOUR_TOKEN_HERE
```

## Step 6: Test the API

Run the test script to verify all endpoints:

```bash
./test_api.sh
```

Expected output:
```
===================================
VelociCompanion API Test Script
===================================

1. Testing health endpoint...
✓ Health check passed

2. Registering a new user...
✓ User registration successful

3. Logging in...
✓ Login successful

4. Getting current user profile...
✓ Profile retrieval successful

5. Listing tenants...
✓ Tenants list retrieved

6. Listing hosts...
Hosts: []

7. Testing authentication protection...
✓ Authentication protection working

===================================
API Testing Complete!
===================================
```

## Common Operations

### Create a Host

```bash
# Get your token from login
TOKEN="your_token_here"

# Create a host
curl -X POST http://localhost:8000/api/hosts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "workstation-01",
    "ip_address": "192.168.1.100",
    "os": "Windows 10"
  }'
```

### List Hosts

```bash
curl -X GET http://localhost:8000/api/hosts \
  -H "Authorization: Bearer $TOKEN"
```

### Ingest Data

```bash
curl -X POST http://localhost:8000/api/ingestion/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "server-01",
    "data": {
      "artifact": "Windows.System.TaskScheduler",
      "results": [...]
    }
  }'
```

## Troubleshooting

### Database Connection Issues

```bash
# Check if database is running
docker-compose logs db

# Restart database
docker-compose restart db
```

### Backend Not Starting

```bash
# Check backend logs
docker-compose logs backend

# Common issues:
# - Database not ready: Wait a few seconds and check logs
# - Port 8000 in use: Stop other services using that port
```

### Frontend Not Loading

```bash
# Check frontend logs
docker-compose logs frontend

# Rebuild frontend if needed
docker-compose build frontend
docker-compose up -d frontend
```

### Reset Everything

```bash
# Stop and remove all containers and volumes
docker-compose down -v

# Start fresh
docker-compose up -d
```

## Next Steps

1. **Create Additional Users**: Use the `/api/auth/register` endpoint
2. **Set Up Tenants**: Create tenants via `/api/tenants` (admin only)
3. **Integrate with Velociraptor**: Configure Velociraptor to send data to `/api/ingestion/ingest`
4. **Explore Cases**: Create and manage threat hunting cases
5. **Configure VirusTotal**: Set up VirusTotal API integration for hash lookups

## Security Considerations

⚠️ **Before deploying to production:**

1. Change the `SECRET_KEY` in docker-compose.yml or .env file
   - Must be at least 32 characters
   - Use a cryptographically random string

2. Use strong passwords for the database

3. Enable HTTPS/TLS for API and frontend

4. Configure proper firewall rules

5. Review and update CORS settings in `backend/app/main.py`

## Development Mode

To run in development mode with hot reload:

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend (in another terminal)
cd frontend
npm install
npm start
```

## Support

- Documentation: See [README.md](README.md)
- API Docs: http://localhost:8000/docs
- Issues: GitHub Issues
