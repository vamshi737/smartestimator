#!/bin/bash
# backup.sh — simple daily backup script

DATE=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_DIR="backup"
mkdir -p $BACKUP_DIR

# create a zip of source + outputs
zip -r "$BACKUP_DIR/smartestimator_backup_$DATE.zip" src data outputs reports requirements.txt README.md
echo "✅ Backup completed → $BACKUP_DIR/smartestimator_backup_$DATE.zip"
