#!/bin/bash
# backup.sh — simple daily backup script

DATE=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_DIR="backup"
mkdir -p $BACKUP_DIR

zip -r "$BACKUP_DIR/smartestimator_backup_$DATE.zip" src app data output runs reports requirements.txt README.md 2>/dev/null
echo "✅ Backup completed → $BACKUP_DIR/smartestimator_backup_$DATE.zip"
