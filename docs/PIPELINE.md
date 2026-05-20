# Pipeline Reference — Claude API & Digest Drafting

This documents the automated digest pipeline as implemented. The Claude API
integration (`digest.py`) replaced the manual Claude.ai paste workflow.

---

## How `digest.py` works

```
pending_draft.json
       │
       ▼
  load_draft()         ← Prefers pending_draft.json; falls back to weekly_draft_*.json
       │
       ▼
  build_prompt()       ← Compacts items (title, body, source, phase, admin_action, url)
       │                  Inserts into DIGEST_PROMPT_TEMPLATE with week_of and item count
       ▼
  call_claude()        ← claude-sonnet-4-6, max_tokens=4096
       │                  System prompt: SYSTEM_PROMPT (expert M365 technical writer persona)
       ▼
  write_post()         ← Writes site/content/posts/YYYY-MM-DD.md
       │                  Backs up existing file if present (.md.bak)
       ▼
  archive_pending_draft()  ← Moves pending_draft.json → state/archive/pending_draft_YYYY-MM-DD.json
```

---

## System prompt design

The system prompt instructs Claude to:
- Output valid Hugo-flavored Markdown with YAML front matter
- Write in a direct, peer-to-peer engineering tone (no marketing language)
- Structure output: front matter → Top 5 → per-category sections → Action Required → sources shortcode
- Use only the standard tag set (lowercase-hyphenated) and ZT pillar categories
- Map content to Zero Trust pillars: Identity / Devices / Apps / Data / Network / Visibility & Automation
- Surface deadlines, breaking changes, and admin actions prominently

---

## Rolling pending draft

The scraper accumulates items across multiple runs into `state/pending_draft.json`:

- Each run **appends** new items (deduped by ID) to the pending draft
- Per-run snapshots (`weekly_draft_YYYY-MM-DD.json`) are also kept as reference
- On publish, `digest.py` reads the full accumulated draft (all items since last publish)
- After a successful publish, `pending_draft.json` is archived and removed
- The next scraper run starts a fresh accumulation

This means a source being down for one run doesn't cause items to be missed —
they'll appear in the next run's pending draft.

---

## Publish date logic

When consuming `pending_draft.json`, `digest.py` uses **today's date** (publish date)
as the post filename — not the scrape start date. This means the file is always
named for when it actually went live, regardless of how many runs contributed to it.

When consuming a per-run snapshot (fallback), the run's own `week_of` date is used.

---

## API cost

| Model | Est. input tokens | Est. output tokens | Est. per run |
|---|---|---|---|
| claude-sonnet-4-6 | ~15,000–25,000 | ~3,000–4,000 | ~$0.15–0.50 |

Set a spend limit at `console.anthropic.com → Billing → Spend limits`.
$5/month cap is sufficient for weekly runs with headroom for manual re-runs.

---

## Environment

API key is stored on the LXC only — never in the repo:

```
/opt/modern-work-weekly/.env
```

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

`digest.py` loads this via `python-dotenv`. If the file is absent, it falls back
to checking the shell environment directly.

---

## CLI reference

```bash
python digest.py                          # Use pending_draft.json (default)
python digest.py --draft path/to/file     # Use a specific draft file
python digest.py --dry-run                # Print prompt, skip API call
python digest.py --keep-pending           # Don't archive pending draft after publish
```
