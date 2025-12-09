# Deployment Checklist

Use this checklist to deploy VelociCompanion to production.

## Pre-Deployment

### Security Review
- [ ] Generate new SECRET_KEY (minimum 32 characters, cryptographically random)
- [ ] Update DATABASE_URL with production credentials
- [ ] Use strong database password (not default postgres/postgres)
- [ ] Review CORS settings in `backend/app/main.py`
- [ ] Enable HTTPS/TLS for all communications
- [ ] Configure firewall rules
- [ ] Set up VPN or IP whitelist for database access

### Configuration
- [ ] Create production `.env` file
- [ ] Set ACCESS_TOKEN_EXPIRE_MINUTES appropriately (30 minutes recommended)
- [ ] Configure frontend REACT_APP_API_URL
- [ ] Review all environment variables
- [ ] Set up backup strategy for database

### Infrastructure
- [ ] Provision database server or use managed service (RDS, Cloud SQL, etc.)
- [ ] Set up load balancer for backend
- [ ] Configure CDN for frontend static files
- [ ] Set up monitoring and alerting
- [ ] Configure log aggregation
- [ ] Set up automated backups

## Deployment Steps

### 1. Database Setup

```bash
# Create production database
createdb velocicompanion_prod

# Set environment variable
export DATABASE_URL="postgresql://user:pass@host:5432/velocicompanion_prod"

# Run migrations
cd backend
alembic upgrade head
```

### 2. Backend Deployment

```bash
# Build production image
docker build -t velocicompanion-backend:latest ./backend

# Or deploy with docker-compose
docker-compose -f docker-compose.prod.yml up -d backend
```

### 3. Frontend Deployment

```bash
# Build production bundle
cd frontend
npm install
npm run build

# Deploy build/ directory to CDN or web server
# Update API URL in environment
```

### 4. Create Initial Admin User

```bash
# Register first admin user via API
curl -X POST https://your-domain.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "STRONG_PASSWORD_HERE",
    "role": "admin"
  }'
```

### 5. Verify Deployment

```bash
# Check health endpoint
curl https://your-domain.com/health

# Expected: {"status":"healthy"}

# Test authentication
curl -X POST https://your-domain.com/api/auth/login \
  -d "username=admin&password=YOUR_PASSWORD"

# Should return JWT token
```

## Post-Deployment

### Monitoring Setup
- [ ] Configure application monitoring (e.g., Prometheus, Datadog)
- [ ] Set up uptime monitoring (e.g., Pingdom, UptimeRobot)
- [ ] Configure error tracking (e.g., Sentry)
- [ ] Set up log analysis (e.g., ELK stack, CloudWatch)
- [ ] Create dashboards for key metrics

### Alerts
- [ ] High error rate alert
- [ ] Slow response time alert
- [ ] Database connection issues
- [ ] High CPU/memory usage
- [ ] Failed authentication attempts
- [ ] Disk space low

### Backup Verification
- [ ] Verify automated backups are running
- [ ] Test backup restoration process
- [ ] Document backup/restore procedures
- [ ] Set up backup retention policy

### Security
- [ ] Run security scan
- [ ] Review access logs
- [ ] Enable rate limiting
- [ ] Set up intrusion detection
- [ ] Configure SSL certificate auto-renewal

### Documentation
- [ ] Update production endpoints in documentation
- [ ] Document deployment process
- [ ] Create runbook for common issues
- [ ] Train operations team
- [ ] Update architecture diagrams

## Production Environment Variables

### Backend (.env)
```bash
DATABASE_URL=postgresql://user:strongpass@db-host:5432/velocicompanion
SECRET_KEY=your-32-plus-character-secret-key-here-make-it-random
ACCESS_TOKEN_EXPIRE_MINUTES=30
ALGORITHM=HS256
```

### Frontend
```bash
REACT_APP_API_URL=https://api.your-domain.com
```

## Load Balancer Configuration

### Backend
```nginx
upstream backend {
    server backend1:8000;
    server backend2:8000;
    server backend3:8000;
}

server {
    listen 443 ssl;
    server_name api.your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Frontend
```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    root /var/www/velocicompanion/build;
    index index.html;

    location / {
        try_files $uri /index.html;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

## Scaling Considerations

### Horizontal Scaling
- Run multiple backend instances behind load balancer
- Use managed PostgreSQL with read replicas
- Serve frontend from CDN
- Implement caching layer (Redis)

### Vertical Scaling
- **Database**: 4GB RAM minimum, 8GB+ for production
- **Backend**: 2GB RAM per instance, 2+ CPU cores
- **Frontend**: Static files, minimal resources

### Performance Optimization
- [ ] Enable database connection pooling
- [ ] Add Redis cache for sessions
- [ ] Implement request rate limiting
- [ ] Optimize database queries
- [ ] Add database indexes
- [ ] Enable GZIP compression

## Disaster Recovery

### Backup Strategy
- **Database**: Daily full backups, hourly incremental
- **Files**: Daily backup of configuration files
- **Retention**: 30 days of backups
- **Off-site**: Copy backups to different region

### Recovery Procedures
1. Restore database from latest backup
2. Deploy latest application version
3. Run database migrations if needed
4. Verify system functionality
5. Update DNS if needed

### RTO/RPO
- **RTO** (Recovery Time Objective): 4 hours
- **RPO** (Recovery Point Objective): 1 hour

## Maintenance

### Regular Tasks
- [ ] Review logs weekly
- [ ] Update dependencies monthly
- [ ] Security patches: Apply within 7 days
- [ ] Database optimization quarterly
- [ ] Review and rotate access credentials quarterly

### Update Process
1. Test updates in staging environment
2. Schedule maintenance window
3. Notify users of planned downtime
4. Create backup before update
5. Deploy updates
6. Run smoke tests
7. Monitor for issues

## Rollback Plan

If deployment fails:

1. **Immediate**
   ```bash
   # Rollback to previous version
   docker-compose down
   git checkout <previous-tag>
   docker-compose up -d
   ```

2. **Database Rollback**
   ```bash
   # Rollback migration
   alembic downgrade -1
   ```

3. **Verify**
   - Check health endpoint
   - Test critical paths
   - Review error logs

## Support Contacts

- **Technical Lead**: [Contact Info]
- **Database Admin**: [Contact Info]
- **Security Team**: [Contact Info]
- **On-Call**: [Rotation Schedule]

## Success Criteria

- [ ] All services running and healthy
- [ ] Users can login successfully
- [ ] API response times < 500ms
- [ ] Error rate < 1%
- [ ] Database queries optimized
- [ ] Backups running successfully
- [ ] Monitoring and alerts active
- [ ] Documentation updated
- [ ] Team trained on operations

## Sign-Off

- [ ] Technical Lead Approval
- [ ] Security Team Approval
- [ ] Operations Team Approval
- [ ] Product Owner Approval

---

**Deployment Date**: _______________
**Deployed By**: _______________
**Sign-Off**: _______________
