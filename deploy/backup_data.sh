#!/usr/bin/env bash
#
# Daily backup of Atlas Standards data (the JSON "database" + the session
# secret key) to S3. The JSON files are tiny, so we keep every daily archive.
#
# Setup (on the server, once):
#   chmod +x /home/ubuntu/CommunitiesQualifier/deploy/backup_data.sh
#   sudo apt-get install -y awscli        # if the AWS CLI isn't installed
#   # add to crontab (runs 03:10 every day):
#   crontab -e
#   10 3 * * * /home/ubuntu/CommunitiesQualifier/deploy/backup_data.sh >> /var/log/atlas-backup.log 2>&1
#
# Restore (manual): download an archive and untar it into the data/ folder:
#   aws s3 cp s3://atlas-standards-uploads/backups/2026/06/atlas-data-XXXX.tar.gz .
#   tar -xzf atlas-data-XXXX.tar.gz -C /home/ubuntu/CommunitiesQualifier/app_mantenimiento/data/
#   sudo systemctl restart atlas
#
set -euo pipefail

DATA_DIR="/home/ubuntu/CommunitiesQualifier/app_mantenimiento/data"
ENV_FILE="/etc/atlas/atlas.env"
BUCKET="atlas-standards-uploads"
PREFIX="backups"
REGION="us-east-2"

# Load ONLY the AWS_* credentials from the env file (cut -d= keeps values intact;
# we avoid `source` because other vars may contain spaces / angle brackets).
if [ -f "$ENV_FILE" ]; then
  AWS_ACCESS_KEY_ID="$(grep -E '^AWS_ACCESS_KEY_ID=' "$ENV_FILE" | head -1 | cut -d= -f2-)"
  AWS_SECRET_ACCESS_KEY="$(grep -E '^AWS_SECRET_ACCESS_KEY=' "$ENV_FILE" | head -1 | cut -d= -f2-)"
  export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
fi
export AWS_DEFAULT_REGION="$REGION"

TS="$(date +%Y%m%d-%H%M%S)"
YM="$(date +%Y/%m)"
TMP="$(mktemp -d)"
ARCHIVE="$TMP/atlas-data-$TS.tar.gz"

# Archive the live JSON data + the persisted secret key (if present).
FILES=$(cd "$DATA_DIR" && ls *.json .secret_key 2>/dev/null || true)
if [ -z "$FILES" ]; then
  echo "$(date -Is) ERROR: no data files found in $DATA_DIR" >&2
  exit 1
fi
tar -czf "$ARCHIVE" -C "$DATA_DIR" $FILES

DEST="s3://$BUCKET/$PREFIX/$YM/atlas-data-$TS.tar.gz"
aws s3 cp "$ARCHIVE" "$DEST" --region "$REGION" --only-show-errors

rm -rf "$TMP"

# Leave a receipt the app can read.
#
# This backup failed every night for two weeks and nobody knew: cron wrote
# "Permission denied" into a log file no human opens. The daily digest reports
# on this file instead, so a backup that stops running shows up in an email
# somebody actually reads. Written only on success — that is the whole point.
echo "$(date -Is) $DEST" > "$DATA_DIR/.last_backup" 2>/dev/null || true

echo "$(date -Is) OK: backup uploaded -> $DEST"
