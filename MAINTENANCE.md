# Modern Work Weekly — Maintenance & Command Reference

Day-to-day and occasional commands for keeping the LXC, the pipeline, and the
site running. Grouped by what you're trying to do.

**SSH target:** `ssh root@10.127.31.35` (hostname `mww`)

> **Convention used in this doc:**
> - 🖥️ **LXC** — run after SSH-ing into the container (`ssh root@10.127.31.35`)
> - 💻 **Local** — run on your Windows machine (PowerShell, from the repo directory)

---

## OS / system maintenance (LXC)

🖥️ **LXC**
```bash
# Update package lists and upgrade installed packages
apt update && apt upgrade -y

# Reboot if a kernel/critical update requires it
reboot

# Check disk space (the LXC is small — 8–20 GB disk)
df -h

# Check memory usage (512 MB RAM — tight)
free -h

# Check what's running / service health
systemctl status caddy
systemctl status cloudflared
systemctl status cron

# Restart a service if needed
systemctl restart caddy
systemctl restart cloudflared
```

---

## Checking on the automation (logs & cron)

🖥️ **LXC**
```bash
# See all three scheduled jobs
crontab -l

# Tail the relevant logs
tail -f /var/log/mww-weekly.log       # Tuesday full-pipeline run
tail -f /var/log/mww-deploy.log       # 5-minute deploy cron
tail -f /opt/modern-work-weekly/logs/health.log   # 8-hour health refresh
ls /opt/modern-work-weekly/logs/      # per-source scraper logs (scraper_YYYYMMDD.log)

# Confirm the Tuesday cron actually fired
cd /opt/modern-work-weekly/repo && git log --oneline -5
```

---

## Running the pipeline manually

🖥️ **LXC** — always activate the venv first:

```bash
source /opt/modern-work-weekly/scraper/.venv/bin/activate
cd /opt/modern-work-weekly/repo/scraper
```

🖥️ **LXC**
```bash
# --- Scraper ---
python scraper.py                    # normal run, accumulates new items
python scraper.py --force-all        # bypass dedup, pull everything (used for Tuesday + testing)
python scraper.py --source Intune    # test a single source (swap in any source name)
python scraper.py --health-only      # refresh health.json only, no draft/state changes

# --- Digest / drafting ---
python digest.py                     # full run: technical digest + Exec Guide + LinkedIn draft
python digest.py --skip-exec         # skip the Executive's Guide
python digest.py --skip-linkedin     # skip the LinkedIn newsletter draft
python digest.py --dry-run           # print the prompt only, no API call (sanity check)
python digest.py --keep-pending      # don't archive pending_draft.json (handy for re-testing)
python digest.py --draft ../state/weekly_draft_2026-05-20.json   # run against an old snapshot

# --- Full cron scripts (run end-to-end as the cron would) ---
chmod +x weekly-run.sh && ./weekly-run.sh     # full Tuesday pipeline + immediate deploy
chmod +x health-run.sh && ./health-run.sh     # known-issues refresh + push if changed
chmod +x deploy.sh && ./deploy.sh             # manual pull + build + deploy
```

> **Note:** `git reset --hard` (see Git section) resets file permissions too —
> if you hit `Permission denied` on a `.sh` script after a reset/checkout, just
> `chmod +x <script>.sh` again.

---

## Updating sources (what gets scraped)

All source definitions live in `scraper/sources.py`.

🖥️ **LXC**
```bash
nano /opt/modern-work-weekly/repo/scraper/sources.py
```

To **add a source**: add an entry to the `SOURCES` list with the portal URL.
Prefer an RSS feed where one exists (more reliable than HTML scraping). Set
`health=True` if it's a known-issues page that should feed the health
sidebar/widget instead of (or in addition to) the regular digest.

To **test a new/changed source** before trusting it in the real pipeline:

🖥️ **LXC**
```bash
python scraper.py --source <SourceName>
tail -50 /opt/modern-work-weekly/logs/scraper_$(date +%Y%m%d).log
```

After editing, commit and push like any other code change (see Git section).

---

## Reviewing & correcting a published digest

💻 **Local**
```powershell
# Pull the week's posts down
cd path/to/modern-work-weekly
git pull

# Open and edit:
#   site/content/posts/YYYY-MM-DD.md   (technical digest)
#   site/content/exec/YYYY-MM-DD.md    (Executive's Guide)
```

The LinkedIn draft lives on the LXC (it's gitignored). Copy it to your local machine first:

💻 **Local**
```powershell
scp root@10.127.31.35:/opt/modern-work-weekly/repo/state/linkedin_draft_YYYY-MM-DD.txt .
```

After editing the digest and/or exec guide:

💻 **Local**
```powershell
git add site/content/posts/YYYY-MM-DD.md site/content/exec/YYYY-MM-DD.md
git commit -m "digest: YYYY-MM-DD — editorial pass"
git push origin main
# deploy.sh picks this up within 5 minutes — no manual deploy step needed
```

LinkedIn format reference: `linkedin/template.md`, formatter: `linkedin/formatter.py`.

---

## Git workflow basics (for this repo)

**Repo directory:** `C:\Users\Ryan\OneDrive\Documents\Projects\Claude-Accessible\modern-work-weekly\modern-work-weekly`

💻 **Local** — standard day-to-day workflow:
```powershell
# Standard sync before doing anything
git pull origin main

# After making changes
git add <files>
git commit -m "description"
git push origin main
```

### Push rejected (remote has commits you don't)

If `git push` fails with "fetch first" / "non-fast-forward", the LXC bot has pushed since your last pull. If you have no unstaged changes:

```powershell
git pull --rebase origin main
git push origin main
```

If you **do** have unstaged changes (Git will say "cannot pull with rebase: You have unstaged changes"), stash them first, then rebase, then restore:

```powershell
git stash
git pull --rebase origin main
git push origin main
git stash pop
```

> **Note:** Run each command separately — pasting them as one line will break. After `git stash pop`, Git may report modified/untracked files that were stashed (e.g. `.gitignore`, `state/linkedin_draft_*.txt`); those are fine to leave unstaged unless you intended to commit them.

### Nuclear option — discard local commits, match remote exactly

```powershell
git fetch origin
git reset --hard origin/main
```

🖥️ **LXC** — git identity for automated commits (`mww-bot`):
```bash
git config --global user.name "mww-bot"
git config --global user.email "bot@yourdomain.com"
```

---

## Deploy & site troubleshooting

🖥️ **LXC**
```bash
# Confirm the deploy cron is registered
crontab -l   # look for the */5 * * * * deploy.sh entry

# Check whether the latest commit landed on disk
ls -la /opt/modern-work-weekly/site/public/posts/

# Tail the deploy log for "New commits detected... Deploy done"
tail -f /var/log/mww-deploy.log

# Manual rebuild + deploy (bypasses the cron / does it right now)
cd /opt/modern-work-weekly/repo/site
hugo --minify --baseURL "https://modernworkweekly.com"
rsync -av public/ /opt/modern-work-weekly/site/public/
chown -R www-data:www-data /opt/modern-work-weekly/site/public/

# Check the reverse proxy and tunnel
systemctl status caddy
systemctl status cloudflared
cloudflared tunnel info modern-work-weekly
```

If the **GitHub Actions** badge goes red: it's a CI build-check only (does not
deploy, doesn't affect the live site). Check the Actions tab for the actual
Hugo build error — usually a template/content syntax issue.

### Social link previews blocked (LinkedIn, Slack, Twitter/X)

If links to the site work fine in a browser but show "content blocked" or fail to unfurl when shared on social platforms, Cloudflare's bot protection is the likely cause. Social crawlers don't behave like normal browsers and get flagged.

**Fix:** `dash.cloudflare.com` → `modernworkweekly.com` → **Security → Settings** → scroll down and disable:
- **Bot Fight Mode**
- **Browser Integrity Check**

This affects all social preview crawlers, not just LinkedIn.

### Site changes pushed but not appearing live ("stuck" deploy)

Happened for real on 2026-07-17: production sat 13 commits behind `origin/main`
for weeks — the whole Modern Work taxonomy reframe plus everything after it —
with no error visible anywhere until someone went looking.

**Root cause:** `site/data/deadlines.json` gets rewritten by every
`purge_expired_deadlines()` run (its `"updated"` timestamp changes even when
nothing actually expired), but nothing on the LXC ever commits that file. It
sits as harmless local drift — until a commit on `origin/main` *also* touches
`deadlines.json` (e.g. adding a new Key Date from the local repo), at which
point `git pull` refuses to fast-forward. `weekly-run.sh` already discards
this drift before pulling; `health-run.sh` didn't (fixed 2026-07-17). Once one
cron's pull starts failing this way, every other cron hits the identical
conflict, and `deploy.sh`'s pull failure was silent (also hardened
2026-07-17) — so the site just quietly stops updating with nothing in the
log to flag it.

🖥️ **LXC — check first, whenever "I pushed X but the site doesn't show it":**
```bash
cd /opt/modern-work-weekly/repo
git status                    # anything modified/untracked on a tracked file?
git log --oneline -3          # compare HEAD against the latest commit on GitHub
```
If `git status` shows local changes to a tracked file (`site/data/deadlines.json`
is the usual suspect) and `HEAD` is behind GitHub's `main`:
```bash
git checkout -- site/data/deadlines.json site/data/health.json
git pull
```
Then force the build once, since you just pulled manually and `deploy.sh`'s
own next pull will see nothing new to fast-forward and skip the rebuild:
```bash
cd /opt/modern-work-weekly/repo/site
hugo --minify --baseURL "https://modernworkweekly.com"
rsync -av --delete public/ /opt/modern-work-weekly/site/public/
```

**Also check** whenever debugging a stuck deploy: any script written
directly on the LXC (outside the repo's normal edit-locally-push-pull flow)
stays untracked and invisible to the repo — `git status` surfaces those too
under "Untracked files." Commit anything worth keeping (`git add`, `git commit`,
`git push`), then `git pull` on your local machine so both clones agree.

---

## API / cost management

🖥️ **LXC**
```bash
# Verify the Anthropic API key is in place
cat /opt/modern-work-weekly/.env   # should show ANTHROPIC_API_KEY=sk-ant-...
```

- Set/check spend limits at `console.anthropic.com → Billing → Spend limits`
  (a $10/month cap covers weekly runs + manual re-runs with headroom)
- Typical cost: **$0.30–1.00 per Tuesday run** across all 3 Claude calls

---

## Quick-reference: what lives where

| Need to... | Look at / edit |
|---|---|
| Change what gets scraped | `scraper/sources.py` |
| Change how Claude drafts content | `scraper/digest.py` (system prompts) |
| Change site look/layout | `site/layouts/`, `site/static/css/`, `site/static/js/` |
| Change site config (title, menus, params) | `site/hugo.toml` |
| See/adjust known issues data | `site/data/health.json` (auto-managed — don't hand-edit normally) |
| See/adjust deadlines | `site/data/deadlines.json` (auto-purged every 8h) |
| Check what's been scraped/seen before | `state/seen_items.json`, `state/pending_draft.json` |
| Reverse proxy config | `infra/caddy/Caddyfile` → `/etc/caddy/Caddyfile` on the LXC |
| Tunnel config | `infra/cloudflare/tunnel.yml` → `/etc/cloudflared/config.yml` on the LXC |
| Fresh-LXC setup from scratch | `infra/lxc/bootstrap.sh`, and walk through `docs/SETUP.md` |

---

## Routine maintenance checklist

```
[ ] Weekly: review Tuesday's digest + Exec Guide + LinkedIn draft, push corrections
[ ] Monthly: apt update && apt upgrade on the LXC; reboot if needed
[ ] Monthly: check Anthropic billing/spend against the $10 cap
[ ] As needed: add/retire sources in sources.py when Microsoft changes portals
[ ] As needed: check df -h / free -h if the LXC starts feeling sluggish
[ ] Periodically: confirm all 3 crons still registered (`crontab -l`) and logs are rotating (logrotate)
[ ] Weekly: after pushing anything that touches site/data/deadlines.json specifically, confirm it actually landed live (curl modernworkweekly.com/data/deadlines.json) — see "Site changes pushed but not appearing live" above
```
