# Scraper

Collects Microsoft "What's New" updates across all tracked portals, deduplicates against previously seen items, and writes a structured JSON draft for review in Claude.ai.

## Setup

```bash
cd scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
# Normal weekly run (Monday morning)
python scraper.py

# Ignore dedup state — pull everything available
python scraper.py --force-all

# Single source only (useful for testing)
python scraper.py --source Intune
python scraper.py --source Entra
python scraper.py --source Defender
```

## Output

- `../state/weekly_draft_YYYY-MM-DD.json` — structured JSON grouped by category
- `../logs/scraper_YYYYMMDD.log` — run log

## After running

1. Open `state/weekly_draft_YYYY-MM-DD.json`
2. Open Claude.ai → your "Modern Work Weekly" Project
3. Paste the JSON into the chat
4. Claude uses the saved master prompt to generate the full digest
5. Copy the digest into `site/content/posts/YYYY-MM-DD.md`

## Adding new sources

Edit `sources.py` — add a new entry to the `SOURCES` list with the portal URL. If it has an RSS feed, provide that — RSS is always preferred over HTML scraping.

## Dedup logic

Each item gets a stable SHA-256 hash of `source_name::title`. Seen hashes are stored in `../state/seen_items.json`. On each run, only items with new hashes are included in the draft. If a page updates the wording of an existing item significantly, it will appear as a new item — that's intentional.
