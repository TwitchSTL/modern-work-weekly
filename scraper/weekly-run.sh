#!/bin/bash
# weekly-run.sh — Full Tuesday digest pipeline
#
# 1. Pull latest repo
# 2. Scrape all sources
# 3. Generate digest via Claude API
# 4. Commit new post + health data and push
#
# Cron: 0 7 * * 2 /opt/modern-work-weekly/scraper/weekly-run.sh
# (7 AM UTC every Tuesday = Monday night US Central / Tuesday morning US Eastern)

set -euo pipefail

REPO="/opt/modern-work-weekly/repo"
SCRAPER="/opt/modern-work-weekly/scraper"
VENV="$SCRAPER/.venv/bin/activate"
LOG="/var/log/mww-weekly.log"
DATE=$(date +%Y-%m-%d)

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "===== Weekly run starting (week of $DATE) ====="

# Activate Python venv
# shellcheck disable=SC1090
source "$VENV"

# Sync repo — discard any local health.json drift first so pull succeeds
cd "$REPO"
git checkout -- site/data/health.json 2>/dev/null || true
git pull origin master >> "$LOG" 2>&1
log "Repo up to date"

# Scrape all sources
log "Running scraper..."
python3 "$SCRAPER/scraper.py" --force-all >> "$LOG" 2>&1
log "Scraper done"

# Generate digest
log "Running digest..."
python3 "$SCRAPER/digest.py" >> "$LOG" 2>&1
log "Digest done"

# Commit anything new
cd "$REPO"
git add site/content/posts/ site/data/health.json 2>/dev/null || true

if git diff --cached --quiet; then
  log "Nothing new to commit — skipping push"
else
  git commit -m "digest: week of $DATE"
  git push origin master >> "$LOG" 2>&1
  log "Committed and pushed digest for $DATE"
fi

log "===== Weekly run complete ====="
