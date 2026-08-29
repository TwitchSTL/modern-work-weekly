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

# Guard against racing with weekly-run.sh / health-run.sh's own git pull,
# commit, and push against this same repo. Without this, two processes
# writing refs/remotes/origin/main at once can corrupt the local ref
# ("cannot lock ref ... is at X but expected Y"), and worse, can silently
# desync this script's own BEFORE/AFTER HEAD comparison below so a real
# deploy gets skipped with no error anywhere. Happened for real 2026-08-29:
# three commits landed on disk but were never built because a concurrent
# git operation moved HEAD out from under this script's own pull. This is
# a non-blocking lock (skip and retry in 5 min) since deploy.sh runs so
# often that waiting is pointless -- see MAINTENANCE.md.
LOCK="/var/lock/mww-git.lock"
exec 200>"$LOCK"
if ! flock -n 200; then
  log "Another git/deploy operation is in progress — skipping this cycle, will retry in 5 min."
  exit 0
fi

# Pull latest — exit quietly if already up to date
cd "$REPO"

# Discard local health.json/deadlines.json drift before pulling. Both files
# get their "updated" timestamp rewritten on every scraper/health-run.sh
# pass even when nothing else changed, which otherwise blocks this pull the
# moment an incoming commit also touches either file. weekly-run.sh and
# health-run.sh already do this; deploy.sh didn't, which caused two
# separate silent-deploy outages (2026-07-17, 2026-07-31) before this line
# was added. See MAINTENANCE.md "Site changes pushed but not appearing live."
git checkout -- site/data/health.json site/data/deadlines.json 2>/dev/null || true

BEFORE=$(git rev-parse HEAD)
if ! git pull origin main >> "$LOG" 2>&1; then
  log "ERROR: git pull failed — this box will not receive any updates until this is fixed. Likely cause: local uncommitted changes on a tracked file (run 'git status' on the box) conflicting with an incoming commit. See MAINTENANCE.md."
  exit 1
fi
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
