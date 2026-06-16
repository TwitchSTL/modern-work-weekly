# Weekly Workflow

Three automated cron jobs keep the site current. Your only job is a brief review
after the Tuesday digest publishes.

---

## Automated schedule

### Tuesday 5:55 AM CST — Full digest pipeline

`weekly-run.sh` runs end-to-end:

1. **`git pull origin main`** — syncs the repo to latest (first discards any local
   `health.json`/`deadlines.json` drift so the pull applies cleanly)
2. **`scraper.py --force-all`** — fetches 15+ Microsoft portals, deduplicates against
   `seen_items.json`, appends new items to `state/pending_draft.json`, writes known
   issues to `health.json`
3. **`digest.py`** — reads `pending_draft.json`, calls the Claude API three times:
   - Generates technical digest → `site/content/posts/YYYY-MM-DD.md`
   - Generates Executive's Guide → `site/content/exec/YYYY-MM-DD.md`
   - Generates LinkedIn newsletter draft → `state/linkedin_draft_YYYY-MM-DD.txt`
   - Regenerates the search index (`site/static/search.json`) and updates the health baseline
   - Archives `pending_draft.json` to `state/archive/`
4. **`git commit` + `git push origin main`** — if anything changed
5. **Builds and deploys immediately** — runs `hugo --minify` and rsyncs to the web
   root itself (rather than waiting on the 5-minute `deploy.sh` cron, since that cron
   would see "already up to date" right after the LXC's own push)

### Every 5 minutes — Deploy

`deploy.sh` pulls `origin main`; if there are new commits, it rebuilds the Hugo site
and rsyncs `site/public/` to the web root. This is what publishes ordinary `git push`
commits (e.g. your editorial corrections) — **not** GitHub Actions. GitHub Actions only
runs a CI build check on push to `main` (see `.github/workflows/hugo-build.yml`); it
does not deploy to the LXC.

### Every 8 hours — Health/known issues refresh

`health-run.sh` runs a lightweight update:

1. **`git pull`** — syncs the repo to latest
2. **`scraper.py --health-only`** — fetches known-issues sources, overwrites `health.json`,
   and purges expired entries from `site/data/deadlines.json`
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
git push origin main
```

The `deploy.sh` cron picks up the new commit within 5 minutes, rebuilds with Hugo,
and rsyncs to the web root.

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

# Skip the Executive's Guide
python digest.py --skip-exec

# Skip the LinkedIn newsletter draft
python digest.py --skip-linkedin

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

**Executive's Guide or LinkedIn draft fails but digest succeeds**
- Non-fatal — the pipeline continues and logs a warning
- Re-run `python digest.py --keep-pending` to regenerate without re-archiving the pending draft

**GitHub Action fails**
- This is just a CI build check (`hugo --minify` on push to `main`, scoped to `site/**`)
  — it does not deploy. A red check means the Hugo build itself is broken; check the
  Actions tab for the build error
- It does not affect the live site, which is deployed independently by `deploy.sh` on the LXC

**Site not updating after push**
- SSH to LXC: `ls -la /opt/modern-work-weekly/site/public/posts/` — did the file land?
- Check the deploy log: `tail /var/log/mww-deploy.log` — confirm `deploy.sh` picked up the new commit
- Verify the cron is registered: `crontab -l` (look for the `*/5 * * * *` entry)
- Check Caddy: `systemctl status caddy`
- Check tunnel: `systemctl status cloudflared`
- Check tunnel health: `cloudflared tunnel info modern-work-weekly`

**health.json stale**
- Check the health log: `tail /opt/modern-work-weekly/logs/health.log`
- Run manually: `/opt/modern-work-weekly/repo/scraper/health-run.sh`
- Verify cron is registered: `crontab -l`

**Editing this repo from a sandboxed/cloud-synced clone (e.g. Claude's OneDrive working copy)**
- File edit tools can silently truncate a file mid-write on this mount, even for small
  in-place edits — always verify after editing (`wc -l`, `tail -c 200`, or
  `python3 -c "compile(open(path).read(), path, 'exec')"` for `.py` files) before
  committing. If truncated, recover from git (`git show HEAD:path > /tmp/restore`,
  committed blobs are unaffected) and reapply the edit via a script/heredoc instead.
- `git commit`/`status` can leave stale `.git/index.lock`, `.git/HEAD.lock`, or
  `.git/objects/*/tmp_obj_*` files that block the next git command with "Unable to
  create '...lock': File exists." `rm -f` fails with "Operation not permitted" on this
  mount — `mv` the lock file to a different name instead, then retry immediately
  (don't run another git command in between, or it can re-leave a fresh lock).
- The sandbox has no GitHub credentials — `git push` must be run from a real terminal
  with stored auth, same as the manual-review push in Step 3 above.

---

## Quick checklist

```
[ ] Tuesday cron fired (check: git log --oneline -5)
[ ] Technical digest reviewed and edited if needed
[ ] Executive's Guide reviewed if sharing with leadership
[ ] LinkedIn draft reviewed (state/linkedin_draft_YYYY-MM-DD.txt) before posting manually
    (headlines are auto-linked to their source URL from the technical post — verify a
    few resolve correctly; an unmatched headline is left as plain bold, not a broken link)
[ ] Corrections pushed (if any)
[ ] Site live at modernworkweekly.com
```
