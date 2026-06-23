#!/bin/bash
# deploy.sh — Pull latest repo, build Hugo site, sync to web root
#
# Cron (every 5 min, runs as mww or root):
#   */5 * * * * /opt/modern-work-weekly/repo/scraper/deploy.sh >> /var/log/mww-deploy.log 2>&1

set -euo pipefail

REPO="/opt/modern-work-weekly/repo"
SITE="$REPO/site"
PUBLIC="$SITE/public"
WEB_ROOT="/opt/modern-work-weekly/site/public"
LOG="/var/log/mww-deploy.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# Pull latest — exit quietly if already up to date
cd "$REPO"
BEFORE=$(git rev-parse HEAD)
git pull origin main >> "$LOG" 2>&1
AFTER=$(git rev-parse HEAD)

if [ "$BEFORE" = "$AFTER" ]; then
  exit 0  # Nothing changed — skip build
fi

log "New commits detected ($BEFORE → $AFTER), rebuilding..."

# Build Hugo site
cd "$SITE"
hugo --minify --baseURL "https://modernworkweekly.com" >> "$LOG" 2>&1
log "Hugo build complete"

# Sync to web root — --delete removes stale files when posts are deleted
rsync -av --delete "$PUBLIC/" "$WEB_ROOT/" >> "$LOG" 2>&1
log "Rsync complete"

log "Deploy done"
