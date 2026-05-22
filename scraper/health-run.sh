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

# Pull latest code
cd "$REPO_DIR"
git pull --quiet >> "$LOG_DIR/health.log" 2>&1

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
git push origin master >> "$LOG_DIR/health.log" 2>&1
echo "[$TIMESTAMP] health.json updated and pushed." >> "$LOG_DIR/health.log"
