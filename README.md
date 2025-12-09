# VelociCompanion

A multi-tenant threat hunting companion for Velociraptor with JWT authentication and role-based access control.

## Features

- **JWT Authentication**: Secure token-based authentication system
- **Multi-Tenancy**: Complete data isolation between tenants
- **Role-Based Access Control**: Admin and user roles with different permissions
- **RESTful API**: FastAPI backend with automatic OpenAPI documentation
- **React Frontend**: Modern TypeScript React application with authentication
- **Database Migrations**: Alembic for database schema management
- **Docker Support**: Complete Docker Compose setup for easy deployment

## Project Structure

```
ThreatHunt/
├── backend/
│   ├── alembic/               # Database migrations
│   ├── app/
│   │   ├── api/routes/        # API endpoints
│   │   │   ├── auth.py        # Authentication routes
│   │   │   ├── users.py       # User management
│   │   │   ├── tenants.py     # Tenant management
│   │   │   ├── hosts.py       # Host management
│   │   │   ├── ingestion.py   # Data ingestion
│   │   │   └── vt.py          # VirusTotal integration
│   │   ├── core/              # Core functionality
│   │   │   ├── config.py      # Configuration
│   │   │   ├── database.py    # Database setup
│   │   │   ├── security.py    # Password hashing, JWT
│   │   │   └── deps.py        # FastAPI dependencies
│   │   ├── models/            # SQLAlchemy models
│   │   └── schemas/           # Pydantic schemas
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/        # React components
│   │   ├── context/           # Auth context
│   │   ├── pages/             # Page components
│   │   ├── utils/             # API utilities
│   │   ├── App.tsx
│   │   └── index.tsx
│   ├── package.json
│   └── Dockerfile
└── docker-compose.yml

```

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
- `POST /api/ingestion/ingest` - Ingest data from Velociraptor

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