# Weekly Workflow

Three automated cron jobs keep the site current. Your only job is a brief review
after the Tuesday digest publishes.

---

## Automated schedule

### Tuesday 5:55 AM CST — Full digest pipeline

`weekly-run.sh` runs end-to-end:

1. **`git pull origin main`** — syncs the repo to latest (first discards any local
   `health.json`/`deadlines.json` drift so the pull applies cleanly)
2. **`scraper.py --force-all`** — fetches all 40 Microsoft portals (23 what's-new sources
   + 17 known-issues sources), deduplicates against
   `seen_items.json`, appends new items to `state/pending_draft.json`, writes known
   issues to `health.json`
3. **`digest.py`** — reads `pending_draft.json`, calls the Claude API four times:
   - Generates technical digest → `site/content/posts/YYYY-MM-DD.md`
   - Generates Executive's Guide → `site/content/exec/YYYY-MM-DD.md`
   - Generates LinkedIn newsletter (Pulse article) draft → `state/linkedin_draft_YYYY-MM-DD.txt`
   - Generates LinkedIn announcement/teaser post draft → `state/linkedin_post_YYYY-MM-DD.txt`
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
- **Key Dates** — `digest.py` prints a "Key Date candidates" count after every run (dated retirement/deprecation/GA-target language auto-flagged from this week's items) and writes the detail to `state/deadline_candidates.json`. Candidates pulled from Microsoft 365 Roadmap's own "GA date:"/"Preview date:" line are marked `structured: true` (a Microsoft-confirmed target, not a prose guess) — safe to approve fast, and the `url` on those is already the specific `roadmap?id=...` link. Site data → `site/data/deadlines.json` (rendered on the Key Dates page) is never updated automatically — only the 8-hour cron purge removes expired entries from it. Check the candidates file each week and manually add anything real to `site/data/deadlines.json` with a concrete `date`.
- **Tag candidates** — `digest.py` also writes `state/tag_candidates.json`, one entry per author found on this week's items (from the `author` field `scraper.py` captures off RSS `dc:creator`/Atom `author`). `is_full_name: true` entries are also eligible to be credited by name inline in the Newsletter draft itself; everything else (bare TechCommunity usernames) is review-only — a manual LinkedIn search-and-tag when you post, not an automatic @-mention (LinkedIn only resolves a mention through its own UI autocomplete or a known member URN, neither of which an RSS author name gives us).
- **Sources** — listed in the YAML front matter under `sources:` and rendered at the bottom of each post

### Step 3 — Edit and push corrections

```bash
git add site/content/posts/YYYY-MM-DD.md site/content/exec/YYYY-MM-DD.md
git commit -m "digest: YYYY-MM-DD — editorial pass"
git push origin main
```

The `deploy.sh` cron picks up the new commit within 5 minutes, rebuilds with Hugo,
and rsyncs to the web root.

### Step 4 — Publish to LinkedIn

Two separate pieces, two separate jobs. Don't let the Newsletter edition carry the
click-through job — that's what killed engagement on early editions (see
`feedback_linkedin_hashtags` memory: 4 reactions / 4 comments on a 976-impression
post, with the actual site links buried in self-comments at 65 and 34 impressions).

**`state/linkedin_draft_YYYY-MM-DD.txt`** — the full Newsletter/Pulse article.
Paste as-is into LinkedIn's Newsletter editor and publish. This is for your 132
subscribers who want the whole thing without leaving LinkedIn; it's allowed to be
complete. Its own comments can still carry the Exec's Guide / Technical Digest
links for anyone reading it who wants to go deeper — that's fine, just don't rely
on it to drive general reach.

**`state/linkedin_post_YYYY-MM-DD.txt`** — the short teaser, and the one that
actually needs to work hard. Post it as a regular native feed post, never as an
Article. The first line is `LENS: <name>` — that's editorial metadata for your
review (confirm the chosen angle actually fits this week's strongest item),
strip it before pasting anywhere. Publish order matters:
1. Post the body text only, LENS line removed, no link in it (the draft never
   includes one; keep it that way, an in-body link takes a real reach penalty).
2. The moment it's live, add ONE comment: the `modernworkweekly.com/posts/...`
   link, nothing else. Don't wait, don't also add a second link to the Exec's
   Guide — one link, one destination, immediately, or most readers never see it.
3. Reply to any comments the closing question draws — that's what pulls it into
   more feeds.

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

# Skip the LinkedIn newsletter draft and announcement post
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

**A past week's post/exec content looks incomplete or truncated on the live site**
- This is more likely a silently-failed cron run than a content-generation bug. Check
  whether that week's `weekly-run.sh` invocation actually finished:
  ```bash
  grep -n "=====\|ERROR\|Traceback" /var/log/mww-weekly.log
  ```
  A "Weekly run starting" line with no matching "Weekly run complete" right after it
  means the script died mid-run (it runs under `set -euo pipefail`, so any failed step
  aborts everything after it — including the git commit/push, so nothing reaches the
  live site for that week from that run).
- Pull the first few lines after the failed run's start line to see exactly where it
  died:
  ```bash
  sed -n '<start-line>,<+8>p' /var/log/mww-weekly.log
  ```
- Root cause seen 2026-05-19: `weekly-run.sh` referenced `/opt/modern-work-weekly/scraper/scraper.py`
  (missing the `/repo/` segment), so the scraper step failed immediately with
  `No such file or directory` and the whole run aborted before digest.py ever ran.
  The script has used `SCRAPER_DIR="$REPO/scraper"` since 2026-06-02 and runs since
  then have completed cleanly — but if a similar path/env issue resurfaces, this is
  where it'll show up.
- Don't trust the cron schedule documented in `weekly-run.sh`'s own header comment over
  the real installed entry — compare against:
  ```bash
  crontab -l       # as the user the script is meant to run as (root or mww)
  date              # confirm server timezone — the schedule is in local time, not UTC
  ```
- If content from a failed run was patched by hand afterward (as happened for
  2026-05-19), check `git log --oneline -- <file>` for a string of small "fix:" commits
  on that file — that's the signature of a manual recovery rather than a clean
  automated digest.

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
[ ] LinkedIn Newsletter draft reviewed (state/linkedin_draft_YYYY-MM-DD.txt) before
    posting manually to the Newsletter/Pulse editor
    (headlines are auto-linked to their source URL from the technical post — verify a
    few resolve correctly; an unmatched headline is left as plain bold, not a broken link)
[ ] LinkedIn announcement post reviewed (state/linkedin_post_YYYY-MM-DD.txt) — confirm
    the LENS line matches your editorial judgment, strip it, post the rest as a regular
    feed post, then immediately add the single site link as the first comment
    (see Step 4 above — do not skip straight from posting to walking away)
[ ] Corrections pushed (if any)
[ ] Site live at modernworkweekly.com
```
