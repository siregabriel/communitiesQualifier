#!/usr/bin/env bash
#
# Pulls the latest code, installs dependencies, and restarts the service.
# Run on the Lightsail instance (the GitHub Action calls this on every push).
#
set -euo pipefail

REPO_DIR="${REPO_DIR:-/home/ubuntu/CommunitiesQualifier}"
BRANCH="${BRANCH:-main}"

cd "$REPO_DIR"

echo "==> Pulling latest ($BRANCH)..."
git fetch --quiet origin "$BRANCH"
git reset --hard "origin/$BRANCH"   # fast, deterministic; never touches git-ignored live data

echo "==> Installing dependencies..."
"$REPO_DIR/.venv/bin/pip" install --quiet -r "$REPO_DIR/requirements.txt"

echo "==> Restarting service..."
sudo systemctl restart atlas

echo "==> Deployed $(git rev-parse --short HEAD) at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
