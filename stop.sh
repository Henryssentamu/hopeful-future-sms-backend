#!/usr/bin/env bash
# Stops the backend containers. Your data (MySQL volume) is kept — this
# does NOT wipe the database, it just stops the containers so you can
# start them again later with ./start.sh.
set -euo pipefail
cd "$(dirname "$0")"

sg docker -c "docker compose stop"

echo ""
echo "Backend stopped. Your data is preserved — run ./start.sh to bring it back up."
