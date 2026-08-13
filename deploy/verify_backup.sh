#!/usr/bin/env bash
#
# Restore drill — proves the latest backup can actually be restored.
#
# A backup nobody has restored is a hope, not a backup. This downloads the most
# recent archive, unpacks it into a scratch directory and checks that every
# expected file is present, is valid JSON, and holds a believable number of
# records. It then compares those counts against what is live right now, so a
# backup that silently started capturing nothing shows up immediately.
#
# READ-ONLY. It never writes to the data directory and never touches S3 beyond
# listing and downloading. Safe to run any time, on a live server.
#
#   bash /home/ubuntu/CommunitiesQualifier/deploy/verify_backup.sh
#
# Exit code is 0 when the backup is sound, 1 when something is off — so it can
# be wired into cron later if you want the check to run on its own.

set -uo pipefail

DATA_DIR="/home/ubuntu/CommunitiesQualifier/app_mantenimiento/data"
ENV_FILE="/etc/atlas/atlas.env"
BUCKET="atlas-standards-uploads"
PREFIX="backups"
REGION="us-east-2"
PYTHON="/home/ubuntu/CommunitiesQualifier/.venv/bin/python"

# Same credential handling as the backup script: read only the AWS_* lines,
# because other values in that file contain spaces and angle brackets that
# would break `source`.
#
# Stop here if the credentials can't be read, rather than carrying on and
# calling S3 anonymously. AWS answers an unauthenticated request with
# "AccessDenied", which reads exactly like a missing IAM permission — the first
# run of this script sent us looking at the bucket policy when the real problem
# was a missing sudo.
if [ -f "$ENV_FILE" ]; then
  if [ ! -r "$ENV_FILE" ]; then
    echo "FAIL: $ENV_FILE is not readable by $(whoami)."
    echo "      The credentials live there, so this has to run as root:"
    echo "        sudo bash $0"
    exit 1
  fi
  AWS_ACCESS_KEY_ID="$(grep -E '^AWS_ACCESS_KEY_ID=' "$ENV_FILE" | head -1 | cut -d= -f2-)"
  AWS_SECRET_ACCESS_KEY="$(grep -E '^AWS_SECRET_ACCESS_KEY=' "$ENV_FILE" | head -1 | cut -d= -f2-)"
  export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
fi
export AWS_DEFAULT_REGION="$REGION"

# No key from the file and no instance role either: everything below would fail
# for a reason that has nothing to do with the backups.
if [ -z "${AWS_ACCESS_KEY_ID:-}" ] && ! curl -s -m 2 -o /dev/null \
     http://169.254.169.254/latest/meta-data/iam/security-credentials/ 2>/dev/null; then
  echo "FAIL: no AWS credentials available (none in $ENV_FILE, no instance role)."
  echo "      Nothing below would be a real test of the backup. Run with sudo."
  exit 1
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "Restore drill — $(date -Is)"
echo

# ---- 1. find the most recent archive -------------------------------------
echo "1. Locating the latest backup in S3"
LATEST="$(aws s3 ls "s3://$BUCKET/$PREFIX/" --recursive --region "$REGION" \
          | grep '\.tar\.gz$' | sort | tail -1 | awk '{print $4}')"
if [ -z "$LATEST" ]; then
  echo "   FAIL: no backups found under s3://$BUCKET/$PREFIX/"
  exit 1
fi
SIZE="$(aws s3 ls "s3://$BUCKET/$LATEST" --region "$REGION" | awk '{print $3}')"
echo "   $LATEST  (${SIZE} bytes)"

# ---- 2. download and unpack ----------------------------------------------
echo
echo "2. Downloading and unpacking"
if ! aws s3 cp "s3://$BUCKET/$LATEST" "$WORK/backup.tar.gz" --region "$REGION" --only-show-errors; then
  echo "   FAIL: could not download the archive"
  exit 1
fi
mkdir -p "$WORK/restored"
if ! tar -xzf "$WORK/backup.tar.gz" -C "$WORK/restored"; then
  echo "   FAIL: the archive is corrupt and will not extract"
  exit 1
fi
echo "   extracted $(find "$WORK/restored" -type f | wc -l) files"

# ---- 3. check contents, and compare against what is live -----------------
echo
echo "3. Checking the contents against live data"
"$PYTHON" - "$WORK/restored" "$DATA_DIR" <<'PY'
import json, os, sys

restored, live = sys.argv[1], sys.argv[2]

# file -> the key holding its records, so we can count them
EXPECTED = {
    'inspections.json': 'submissions',
    'regions.json':     'regions',
    'users.json':       'users',
    'questions.json':   'questions',
    'moveins.json':     'moveins',
    'settings.json':    None,
    'profiles.json':    None,
    'activity.json':    'events',
}

def count(path, key):
    """How many records a file holds, or None if it won't parse."""
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return ('unreadable', str(e))
    if key is None:
        return ('ok', len(data) if hasattr(data, '__len__') else 1)
    rows = data.get(key) if isinstance(data, dict) else data
    if isinstance(rows, dict):
        rows = list(rows)
    return ('ok', len(rows) if rows is not None else 0)

problems = []
print(f"   {'file':<20}{'in backup':>12}{'live now':>10}   note")
print('   ' + '-' * 62)
for name, key in EXPECTED.items():
    rp, lp = os.path.join(restored, name), os.path.join(live, name)
    if not os.path.exists(rp):
        # A file that exists live but is missing from the backup is the
        # failure this whole drill is meant to catch.
        note = 'MISSING from backup' if os.path.exists(lp) else 'not present either side'
        if os.path.exists(lp):
            problems.append(f'{name} is missing from the backup')
        print(f"   {name:<20}{'—':>12}{'—' if not os.path.exists(lp) else 'present':>10}   {note}")
        continue
    st, rn = count(rp, key)
    if st != 'ok':
        problems.append(f'{name} in the backup is not valid JSON')
        print(f"   {name:<20}{'BROKEN':>12}{'':>10}   {rn[:38]}")
        continue
    ln = count(lp, key)[1] if os.path.exists(lp) else '—'
    note = ''
    if isinstance(ln, int):
        if rn == 0 and ln > 0:
            problems.append(f'{name} is empty in the backup but has {ln} records live')
            note = 'EMPTY in backup'
        elif isinstance(rn, int) and ln - rn > max(5, ln * 0.5):
            note = 'much smaller than live — check the date'
    print(f"   {name:<20}{rn:>12}{ln:>10}   {note}")

secret = os.path.join(restored, '.secret_key')
print()
print(f"   sign-in key included: {'yes' if os.path.exists(secret) else 'NO — everyone would be signed out on restore'}")
if not os.path.exists(secret) and os.path.exists(os.path.join(live, '.secret_key')):
    problems.append('.secret_key is missing from the backup')

print()
if problems:
    print('   RESULT: the backup has problems')
    for p in problems:
        print(f'     - {p}')
    sys.exit(1)
print('   RESULT: the backup is complete and restorable')
PY
RESULT=$?

echo
if [ $RESULT -eq 0 ]; then
  cat <<'EOS'
Drill passed. To actually restore one day:

  sudo systemctl stop atlas
  cd /home/ubuntu/CommunitiesQualifier/app_mantenimiento
  cp -r data data.before-restore          # keep what is there now
  aws s3 cp s3://atlas-standards-uploads/<archive> /tmp/restore.tar.gz --region us-east-2
  tar -xzf /tmp/restore.tar.gz -C data/
  sudo systemctl start atlas

Photos are not in the archive — they live in S3 already and are untouched by a
data restore.
EOS
else
  echo "Drill FAILED. The backup would not give you a working system — fix this"
  echo "before you need it."
fi
exit $RESULT
