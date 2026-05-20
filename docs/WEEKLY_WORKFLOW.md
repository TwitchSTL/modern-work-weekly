# Weekly Workflow

The pipeline runs automatically every Tuesday at 5:55 AM CST via cron on the LXC.
Your job is to review the draft and push it live when you're satisfied.

---

## What happens automatically (Tuesday 5:55am)

`weekly-run.sh` runs end-to-end:

1. **`git pull`** — syncs the repo to latest
2. **`scraper.py`** — fetches 15+ Microsoft portals, deduplicates against `seen_items.json`,
   appends new items to `state/pending_draft.json`
3. **`digest.py`** — reads `pending_draft.json`, calls Claude API (`claude-sonnet-4-6`),
   writes the draft Hugo post to `site/content/posts/YYYY-MM-DD.md`,
   archives `pending_draft.json` to `state/archive/`
4. **`git push`** — triggers GitHub Actions → Hugo build → deploys to `modernworkweekly.com`

---

## Your weekly review (15–30 min)

### Step 1 — Pull and open the draft

```bash
cd ~/modern-work-weekly
git pull
```

Open `site/content/posts/YYYY-MM-DD.md` in your editor. The post is already live
(pushed by cron), so review promptly — or set `draft: true` in the front matter
before the cron pushes if you prefer to gate publication.

### Step 2 — Review the digest

Check for:
- **Top 5 ranking** — reorder if your judgment disagrees with Claude's
- **Thin items** — any item that's vague or low-signal, cut it or expand it
- **Deadlines** — confirm any action-required items have accurate dates
- **Sources** — if something looks off, the source URL is in the `{{< sources >}}` shortcode at the bottom

### Step 3 — Edit and push corrections

```bash
git add site/content/posts/YYYY-MM-DD.md
git commit -m "digest: YYYY-MM-DD — editorial pass"
git push origin master
```

GitHub Actions rebuilds and redeploys within ~2 minutes.

---

## Running manually

If you need to re-run outside of the Tuesday cron (e.g. sources failed, missed a week):

```bash
ssh root@10.127.31.35

# Run scraper only
cd /opt/modern-work-weekly/repo/scraper
source .venv/bin/activate
python scraper.py

# Run digest only (from existing pending draft)
python digest.py

# Dry run — see the prompt without making an API call
python digest.py --dry-run

# Re-run scraper with dedup bypassed (pulls everything available)
python scraper.py --force-all
```

---

## Troubleshooting

**Scraper returns 0 new items**
- Normal if nothing changed since last run — the pending draft still holds prior items
- Run `--force-all` to bypass dedup and verify sources are responding
- Check `logs/scraper_YYYYMMDD.log` for errors

**Digest fails (API error)**
- Verify `ANTHROPIC_API_KEY` is set in `/opt/modern-work-weekly/.env`
- Check spend limits at `console.anthropic.com → Billing`
- Re-run `python digest.py` — `pending_draft.json` is intact until archiving succeeds

**GitHub Action fails**
- Check the Actions tab — look for rsync or Hugo build errors
- Verify `HOMELAB_HOST`, `HOMELAB_USER`, `HOMELAB_SSH_KEY` secrets are current
- Test SSH: `ssh mww@10.127.31.35`

**Site not updating after push**
- SSH to LXC: `ls -la /opt/modern-work-weekly/site/public/posts/` — did the file land?
- Check Caddy: `systemctl status caddy`
- Check tunnel: `systemctl status cloudflared`
- Check tunnel health: `cloudflared tunnel info modern-work-weekly`

---

## Quick checklist

```
[ ] Tuesday cron fired (check cron log or git log)
[ ] Draft post reviewed and edited if needed
[ ] Corrections pushed (if any)
[ ] Site live at modernworkweekly.com
```
