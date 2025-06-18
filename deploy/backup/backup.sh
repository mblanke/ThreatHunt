#!/bin/bash

# Database backup
BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)

echo "Creating database backup..."
docker exec threat-hunter-db pg_dump -U admin threat_hunter > "$BACKUP_DIR/db_backup_$DATE.sql"

# File uploads backup
echo "Backing up uploads..."
tar -czf "$BACKUP_DIR/uploads_backup_$DATE.tar.gz" ./uploads

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
