#!/bin/bash
# Manual backup script for Ollama Chat database
# Usage: ./backup.sh

set -e

# Load environment variables
if [ -f ../../.env ]; then
    export $(cat ../../.env | grep -v '^#' | xargs)
fi

# Configuration
BACKUP_DIR="../../backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/manual_backup_$TIMESTAMP.sql"
CONTAINER_NAME="ollama_postgres"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "Starting database backup..."
echo "Database: $POSTGRES_DB"
echo "User: $POSTGRES_USER"
echo "Timestamp: $TIMESTAMP"

# Create backup
docker exec -t "$CONTAINER_NAME" pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "✓ Backup completed successfully"
    echo "  File: $BACKUP_FILE"
    echo "  Size: $(du -h "$BACKUP_FILE" | cut -f1)"
else
    echo "✗ Backup failed"
    exit 1
fi

# Optional: Compress the backup
if command -v gzip &> /dev/null; then
    echo "Compressing backup..."
    gzip "$BACKUP_FILE"
    echo "✓ Compressed to $BACKUP_FILE.gz"
fi

# Optional: Clean up old manual backups (keep last 10)
echo "Cleaning up old backups (keeping last 10)..."
ls -t "$BACKUP_DIR"/manual_backup_*.sql* 2>/dev/null | tail -n +11 | xargs -r rm
echo "✓ Cleanup completed"

echo ""
echo "Backup summary:"
echo "  Latest backup: $(ls -t "$BACKUP_DIR"/manual_backup_*.sql* 2>/dev/null | head -1)"
echo "  Total backups: $(ls "$BACKUP_DIR"/manual_backup_*.sql* 2>/dev/null | wc -l)"
