# Scraper

Collects Microsoft "What's New" updates and known issues across all tracked portals,
deduplicates against previously seen items, and builds a rolling pending draft for
the Claude API digest pipeline.

---

## Components

| Script | Role |
|---|---|
| `scraper.py` | Fetches all portals, deduplicates, appends new items to `pending_draft.json` |
| `digest.py` | Reads `pending_draft.json`, calls Claude API, writes Hugo post, archives draft |
| `sources.py` | All source URLs, CSS selectors, RSS feeds, and health-check flags |
| `weekly-run.sh` | Cron entrypoint — pull → scrape → draft → push |

---

## Setup

```bash
cd scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set your Anthropic API key on the LXC (never in the repo):

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' > /opt/modern-work-weekly/.env
chmod 600 /opt/modern-work-weekly/.env
```

---

## Running manually

```bash
# Normal run — accumulates new items into pending_draft.json
python scraper.py

# Ignore dedup state — pull everything available
python scraper.py --force-all

# Single source only (useful for testing a specific portal)
python scraper.py --source Intune
python scraper.py --source Entra
```

```bash
# Generate digest from current pending draft (calls Claude API)
python digest.py

# Dry run — print the prompt without making an API call
python digest.py --dry-run

# Use a specific draft file instead of pending_draft.json
python digest.py --draft ../state/weekly_draft_2026-05-20.json

# Skip archiving pending_draft.json after publish (useful for testing)
python digest.py --keep-pending
```

---

## Output

| File | Description |
|---|---|
| `../state/pending_draft.json` | Rolling accumulator — all new items since last publish |
| `../state/weekly_draft_YYYY-MM-DD.json` | Per-run snapshot (retained for reference) |
| `../state/archive/pending_draft_YYYY-MM-DD.json` | Draft archived after each digest publish |
| `../site/content/posts/YYYY-MM-DD.md` | Hugo post written by `digest.py` |

---

## Automated pipeline (Tuesday 5:55am CST)

`weekly-run.sh` handles the full weekly run:

1. `git pull` — sync repo to latest
2. `scraper.py` — fetch portals, append new items to `pending_draft.json`
3. `digest.py` — call Claude API, write draft Hugo post, archive pending draft
4. `git push` — trigger GitHub Actions → Hugo build → deploy

The draft post is written with `draft: false` and pushed automatically. Review via
the live site or by pulling the repo after the cron fires.

---

## Dedup logic

Each item gets a stable SHA-256 hash of `source_name::title`. Seen hashes are stored
in `../state/seen_items.json`. On each run, only items with new hashes are appended
to the pending draft. If a page updates the wording of an existing item significantly,
it will appear as a new item — that's intentional.

---

## Adding new sources

Edit `sources.py` — add a new entry to the `SOURCES` list with the portal URL.
Prefer RSS feeds over HTML scraping where available. Set `health=True` for known
issues pages that feed the sidebar health widget.
