# Architecture Documentation

This document describes the architecture and design decisions for VelociCompanion.

## System Overview

VelociCompanion is a multi-tenant, cloud-native threat hunting companion designed to work with Velociraptor. It provides secure authentication, data isolation, and role-based access control.

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│             │     │             │     │              │
│  Frontend   │────▶│   Backend   │────▶│  PostgreSQL  │
│  (React)    │     │  (FastAPI)  │     │   Database   │
│             │     │             │     │              │
└─────────────┘     └─────────────┘     └──────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │             │
                    │ Velociraptor│
                    │   Servers   │
                    │             │
                    └─────────────┘
```

## Technology Stack

### Backend
- **FastAPI**: Modern, fast web framework for building APIs
- **SQLAlchemy**: SQL toolkit and ORM
- **PostgreSQL**: Relational database
- **Alembic**: Database migration tool
- **Python-Jose**: JWT token handling
- **Passlib**: Password hashing with bcrypt

### Frontend
- **React**: UI library
- **TypeScript**: Type-safe JavaScript
- **Axios**: HTTP client
- **React Router**: Client-side routing

### Infrastructure
- **Docker**: Containerization
- **Docker Compose**: Multi-container orchestration

## Core Components

### 1. Authentication System

#### JWT Token Flow
```
1. User submits credentials (username/password)
2. Backend verifies credentials
3. Backend generates JWT token with:
   - user_id (sub)
   - tenant_id
   - role
   - expiration time
4. Frontend stores token in localStorage
5. All subsequent requests include token in Authorization header
6. Backend validates token and extracts user context
```

#### Password Security
- Passwords are hashed using bcrypt with automatic salt generation
- Password hashes are never exposed in API responses
- Plaintext passwords are never logged or stored

#### Token Security
- Tokens expire after 30 minutes (configurable)
- Tokens are signed with HS256 algorithm
- Secret key must be at least 32 characters

### 2. Multi-Tenancy

#### Data Isolation
Every database query is automatically scoped to the user's tenant:

```python
# Example: Listing hosts
hosts = db.query(Host).filter(Host.tenant_id == current_user.tenant_id).all()
```

#### Tenant Creation
- Default tenant is created automatically on first user registration
- Admin users can create additional tenants
- Users are assigned to exactly one tenant

#### Cross-Tenant Access
- Regular users: Can only access data in their tenant
- Admin users: Can access all data in their tenant
- Super-admin (future): Could access multiple tenants

### 3. Role-Based Access Control (RBAC)

#### Roles
- **user**: Standard user with read/write access to their tenant's data
- **admin**: Elevated privileges within their tenant
  - Can manage users in their tenant
  - Can create/modify/delete resources
  - Can view all data in their tenant

#### Permission Enforcement
```python
# Endpoint requiring admin role
@router.get("/users")
async def list_users(
    current_user: User = Depends(require_role(["admin"]))
):
    # Only admins can access this
    pass
```

### 4. Database Schema

#### Core Tables

**tenants**
- id (PK)
- name (unique)
- description
- created_at

**users**
- id (PK)
- username (unique)
- password_hash
- role
- tenant_id (FK → tenants)
- is_active
- created_at

**hosts**
- id (PK)
- hostname
- ip_address
- os
- tenant_id (FK → tenants)
- host_metadata (JSON)
- created_at
- last_seen

**cases**
- id (PK)
- title
- description
- status (open, closed, investigating)
- severity (low, medium, high, critical)
- tenant_id (FK → tenants)
- created_at
- updated_at

**artifacts**
- id (PK)
- artifact_type (hash, ip, domain, email, etc.)
- value
- description
- case_id (FK → cases)
- artifact_metadata (JSON)
- created_at

#### Relationships
```
tenants (1) ──< (N) users
tenants (1) ──< (N) hosts
tenants (1) ──< (N) cases
cases (1) ──< (N) artifacts
```

### 5. API Design

#### RESTful Principles
- Resources are nouns (users, hosts, cases)
- HTTP methods represent actions (GET, POST, PUT, DELETE)
- Proper status codes (200, 201, 401, 403, 404)

#### Authentication
All endpoints except `/auth/register` and `/auth/login` require authentication.

```
Authorization: Bearer <jwt_token>
```

#### Response Format
Success:
```json
{
  "id": 1,
  "username": "john",
  "role": "user",
  "tenant_id": 1
}
```

Error:
```json
{
  "detail": "User not found"
}
```

### 6. Frontend Architecture

#### Component Structure
```
src/
├── components/        # Reusable UI components
│   └── PrivateRoute.tsx
├── context/          # React Context providers
│   └── AuthContext.tsx
├── pages/           # Page components
│   ├── Login.tsx
│   └── Dashboard.tsx
├── utils/           # Utilities
│   └── api.ts       # API client
├── App.tsx          # Main app component
└── index.tsx        # Entry point
```

#### State Management
- **AuthContext**: Global authentication state
  - Current user
  - Login/logout functions
  - Loading state
  - Authentication status

#### Routing
```
/login        → Login page (public)
/             → Dashboard (protected)
/*            → Redirect to / (protected)
```

### 7. Security Architecture

#### Authentication Flow
1. Frontend sends credentials to `/api/auth/login`
2. Backend validates and returns JWT token
3. Frontend stores token in localStorage
4. Token included in all API requests
5. Backend validates token on each request

#### Authorization Flow
1. Extract JWT from Authorization header
2. Verify token signature and expiration
3. Extract user_id from token payload
4. Load user from database
5. Check user's role for endpoint access
6. Apply tenant scoping to queries

#### Security Headers
```python
# CORS configuration
allow_origins=["http://localhost:3000"]
allow_credentials=True
allow_methods=["*"]
allow_headers=["*"]
```

## Data Flow Examples

### User Registration
```
1. POST /api/auth/register
   {username: "john", password: "pass123"}
2. Backend hashes password
3. Create default tenant if needed
4. Create user record
5. Return user object (without password_hash)
```

### Host Ingestion
```
1. Velociraptor sends data to POST /api/ingestion/ingest
   - Must include valid JWT token
2. Extract tenant_id from current user
3. Find or create host with hostname
4. Update host metadata
5. Return success response
```

### Listing Resources
```
1. GET /api/hosts with Authorization header
2. Validate JWT token
3. Extract tenant_id from user
4. Query: SELECT * FROM hosts WHERE tenant_id = ?
5. Return filtered results
```

## Deployment Architecture

### Development
```
┌──────────────────────────────────────┐
│           Docker Compose              │
├──────────────────────────────────────┤
│  Frontend:3000  Backend:8000  DB:5432│
└──────────────────────────────────────┘
```

### Production (Recommended)
```
┌─────────────┐     ┌─────────────┐
│   Nginx/    │     │  Frontend   │
│   Traefik   │────▶│  (Static)   │
│   (HTTPS)   │     └─────────────┘
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│   Backend   │     │  PostgreSQL  │
│  (Multiple  │────▶│  (Managed)   │
│  instances) │     └──────────────┘
└─────────────┘
```

## Performance Considerations

### Database Indexing
- Primary keys on all tables
- Unique index on usernames
- Index on tenant_id columns for fast filtering
- Index on hostname for host lookups

### Query Optimization
- Always filter by tenant_id early in queries
- Use pagination for large result sets (skip/limit)
- Lazy load relationships when not needed

### Caching (Future)
- Cache tenant information
- Cache user profiles
- Cache frequently accessed hosts

## Monitoring & Logging

### Health Checks
```
GET /health → {"status": "healthy"}
```

### Logging
- Request logging via Uvicorn
- Error tracking in application logs
- Database query logging (development only)

### Metrics (Future)
- Request count per endpoint
- Authentication success/failure rate
- Database query performance
- Active user count

## Migration Strategy

### Database Migrations
```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Schema Evolution
1. Create migration for schema changes
2. Test migration in development
3. Apply to staging environment
4. Verify data integrity
5. Apply to production during maintenance window

## Testing Strategy

### Unit Tests (Future)
- Test individual functions
- Mock database connections
- Test password hashing
- Test JWT token creation/verification

### Integration Tests (Future)
- Test API endpoints
- Test authentication flow
- Test multi-tenancy isolation
- Test RBAC enforcement

### Manual Testing
- Use test_api.sh script
- Use FastAPI's /docs interface
- Test frontend authentication flow

## Future Enhancements

### Phase 2
- Refresh tokens for longer sessions
- Password reset functionality
- Email verification
- Two-factor authentication (2FA)

### Phase 3
- Audit logging
- Advanced search and filtering
- Real-time notifications
- Velociraptor direct integration

### Phase 4
- Machine learning for threat detection
- Automated playbooks
- Integration with SIEM systems
- Advanced reporting and analytics

## Troubleshooting Guide

### Common Issues

**Token Expired**
- Tokens expire after 30 minutes
- User must login again
- Consider implementing refresh tokens

**Permission Denied**
- User lacks required role
- Check user's role in database
- Verify endpoint requires correct role

**Data Not Visible**
- Check tenant_id of user
- Verify data belongs to correct tenant
- Ensure tenant_id is being applied to queries

**Database Connection Failed**
- Check DATABASE_URL environment variable
- Verify PostgreSQL is running
- Check network connectivity

## Development Guidelines

### Adding New Endpoints

1. Create route in `app/api/routes/`
2. Add authentication dependency
3. Apply tenant scoping to queries
4. Add role check if needed
5. Create Pydantic schemas
6. Update router registration in main.py
7. Test with /docs interface

### Adding New Models

1. Create model in `app/models/`
2. Add tenant_id foreign key
3. Create migration
4. Create Pydantic schemas
5. Create CRUD routes
6. Apply tenant scoping

### Code Style

- Follow PEP 8 for Python
- Use type hints
- Write docstrings for functions
- Keep functions small and focused
- Use meaningful variable names

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [JWT RFC](https://tools.ietf.org/html/rfc7519)
- [OAuth 2.0 RFC](https://tools.ietf.org/html/rfc6749)
