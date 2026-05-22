# Weekly Workflow

Two automated cron jobs keep the site current. Your only job is a brief review
after the Tuesday digest publishes.

---

## Automated schedule

### Tuesday 5:55 AM CST — Full digest pipeline

`weekly-run.sh` runs end-to-end:

1. **`git pull`** — syncs the repo to latest
2. **`scraper.py`** — fetches 15+ Microsoft portals, deduplicates against `seen_items.json`,
   appends new items to `state/pending_draft.json`, writes known issues to `health.json`
3. **`digest.py`** — reads `pending_draft.json`, calls Claude API:
   - Generates technical digest → `site/content/posts/YYYY-MM-DD.md`
   - Generates Executive's Guide → `site/content/exec/YYYY-MM-DD.md`
   - Archives `pending_draft.json` to `state/archive/`
4. **`git push`** — triggers GitHub Actions → Hugo build → deploys to `modernworkweekly.com`

### Every 8 hours — Health/known issues refresh

`health-run.sh` runs a lightweight update:

1. **`git pull`** — syncs the repo to latest
2. **`scraper.py --health-only`** — fetches known-issues sources only, overwrites `health.json`
3. **`git push`** — only if `health.json` content actually changed (no empty commits)

---

## Your weekly review (15–30 min)

### Step 1 — Pull and open the draft

On your local machine:
```bash
cd path/to/modern-work-weekly
git pull
```

Open `site/content/posts/YYYY-MM-DD.md` in your editor. The post is already live
(pushed by cron), so review promptly — or set `draft: true` in the front matter
before the cron pushes if you prefer to gate publication.

The companion Executive's Guide is at `site/content/exec/YYYY-MM-DD.md`.

### Step 2 — Review the digest

Check for:
- **Top 5 ranking** — reorder if your judgment disagrees with Claude's
- **Thin items** — any item that's vague or low-signal, cut it or expand it
- **Deadlines** — confirm any action-required items have accurate dates
- **Sources** — listed in the YAML front matter under `sources:` and rendered at the bottom of each post

### Step 3 — Edit and push corrections

```bash
git add site/content/posts/YYYY-MM-DD.md site/content/exec/YYYY-MM-DD.md
git commit -m "digest: YYYY-MM-DD — editorial pass"
git push origin master
```

GitHub Actions rebuilds and redeploys within ~2 minutes.

---

## Running manually

If you need to re-run outside of the Tuesday cron (e.g. sources failed, missed a week):

```bash
ssh root@10.127.31.35

# Activate the venv
source /opt/modern-work-weekly/scraper/.venv/bin/activate

cd /opt/modern-work-weekly/repo/scraper

# Run scraper only — accumulate items into pending_draft.json
python scraper.py

# Run digest only — reads existing pending_draft.json
python digest.py

# Technical digest only — skip the Executive's Guide
python digest.py --skip-exec

# Dry run — see the prompt without making an API call
python digest.py --dry-run

# Re-run scraper with dedup bypassed — pulls everything available
python scraper.py --force-all

# Health-only refresh — useful for forcing a health.json update
python scraper.py --health-only
```

---

## Troubleshooting

**Scraper returns 0 new items**
- Normal if nothing changed since last run — the pending draft still holds prior items
- Run `--force-all` to bypass dedup and verify sources are responding
- Check `logs/scraper_YYYYMMDD.log` for per-source errors

**Digest fails (API error)**
- Verify `ANTHROPIC_API_KEY` is set in `/opt/modern-work-weekly/.env`
- Check spend limits at `console.anthropic.com → Billing`
- Re-run `python digest.py` — `pending_draft.json` is intact until archiving succeeds

**Executive's Guide fails but digest succeeds**
- Non-fatal — the pipeline continues and logs a warning
- Re-run `python digest.py --keep-pending` to regenerate both without re-archiving

**GitHub Action fails**
- Check the Actions tab — look for rsync or Hugo build errors
- Verify `HOMELAB_HOST`, `HOMELAB_USER`, `HOMELAB_SSH_KEY` secrets are current
- Test SSH from a local machine: `ssh mww@10.127.31.35`

**Site not updating after push**
- SSH to LXC: `ls -la /opt/modern-work-weekly/site/public/posts/` — did the file land?
- Check Caddy: `systemctl status caddy`
- Check tunnel: `systemctl status cloudflared`
- Check tunnel health: `cloudflared tunnel info modern-work-weekly`

**health.json stale**
- Check the health log: `tail /opt/modern-work-weekly/logs/health.log`
- Run manually: `/opt/modern-work-weekly/repo/scraper/health-run.sh`
- Verify cron is registered: `crontab -l`

---

## Quick checklist

```
[ ] Tuesday cron fired (check: git log --oneline -5)
[ ] Technical digest reviewed and edited if needed
[ ] Executive's Guide reviewed if sharing with leadership
[ ] Corrections pushed (if any)
[ ] Site live at modernworkweekly.com
```
