#!/usr/bin/env bash
# Starts the backend (MySQL + Redis + Django) in the background.
# Works whether or not your current shell session already has docker
# group membership applied (sg docker -c is a no-op if you're already in
# the group, and picks up the group if you're not).
set -euo pipefail
cd "$(dirname "$0")"

sg docker -c "docker compose up -d"

echo ""
echo "Backend starting — API will be live at http://localhost:8000/api/"
echo "Check status with: docker compose ps"
