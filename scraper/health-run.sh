#!/bin/bash
# health-run.sh — Scrape known-issues sources and push health.json if changed.
# Designed to run every 8 hours via cron on the LXC host.
# Cron entry: 0 */8 * * * /opt/modern-work-weekly/repo/scraper/health-run.sh

set -euo pipefail

REPO_DIR="/opt/modern-work-weekly/repo"
SCRAPER_DIR="$REPO_DIR/scraper"
VENV_DIR="/opt/modern-work-weekly/scraper/.venv"
LOG_DIR="/opt/modern-work-weekly/logs"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

mkdir -p "$LOG_DIR"
echo "[$TIMESTAMP] Health scraper starting..." >> "$LOG_DIR/health.log"

# Pull latest code — discard any local health.json/deadlines.json drift
# first, same as weekly-run.sh. Without this, a routine purge write here
# (purge_expired_deadlines() rewrites deadlines.json's "updated" timestamp
# on every run, even a no-op purge) leaves that file locally modified.
# That's harmless in isolation, but the instant any commit on origin/main
# also touches deadlines.json, this pull refuses to fast-forward — and
# since deploy.sh's 5-minute pull hits the identical conflict with no
# error surfaced, the whole site silently stops receiving updates until
# someone notices and clears the drift by hand. See MAINTENANCE.md.
cd "$REPO_DIR"
git checkout -- site/data/health.json site/data/deadlines.json 2>/dev/null || true
if ! git pull --quiet >> "$LOG_DIR/health.log" 2>&1; then
    echo "[$TIMESTAMP] ERROR: git pull failed — check for local drift on tracked files (git status) or a merge conflict. Site will not receive updates until this is resolved." >> "$LOG_DIR/health.log"
    exit 1
fi

# Activate venv and run health-only scrape
source "$VENV_DIR/bin/activate"
python "$SCRAPER_DIR/scraper.py" --health-only >> "$LOG_DIR/health.log" 2>&1

# Only push if health.json actually changed — avoids noisy empty commits
if git diff --quiet site/data/health.json; then
    echo "[$TIMESTAMP] health.json unchanged — no push needed." >> "$LOG_DIR/health.log"
    exit 0
fi

git add site/data/health.json
git commit -m "health: auto-update known issues"
git push origin main >> "$LOG_DIR/health.log" 2>&1
echo "[$TIMESTAMP] health.json updated and pushed." >> "$LOG_DIR/health.log"
