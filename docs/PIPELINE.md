# Pipeline Reference — Claude API & Digest Drafting

Documents the automated digest pipeline as implemented. Two Claude API calls are
made per Tuesday run — one for the technical digest, one for the Executive's Guide.

---

## How `digest.py` works

```
pending_draft.json
       │
       ▼
  load_draft()              ← Prefers pending_draft.json; falls back to weekly_draft_*.json
       │
       ├─────────────────────────────────────────────────┐
       ▼                                                 ▼
  build_prompt()                                   build_exec_prompt()
  call_claude()                                    call_claude_exec()
  write_post()                                     write_exec_post()
       │                                                 │
       ▼                                                 ▼
  site/content/posts/                          site/content/exec/
  YYYY-MM-DD.md                                YYYY-MM-DD.md
       │
       ▼
  archive_pending_draft()   ← Moves pending_draft.json → state/archive/pending_draft_YYYY-MM-DD.json
```

---

## System prompt design

### Technical digest (`SYSTEM_PROMPT`)

Instructs Claude to:
- Output valid Hugo-flavored Markdown with YAML front matter
- Write in a direct, peer-to-peer engineering tone (no marketing language)
- Structure: front matter → Top 5 → per-category sections → Action Required
- List all source URLs in the YAML front matter under a `sources:` key (not in the post body)
- Use only the standard lowercase-hyphenated tag set
- Map content to Zero Trust pillars: Identity / Devices / Apps / Data / Network / Visibility & Automation
- Surface deadlines, breaking changes, and admin actions prominently

### Executive's Guide (`EXEC_SYSTEM_PROMPT`)

Instructs Claude to:
- Write for C-suite, IT directors, compliance officers — no unexplained jargon
- Structure: front matter → Week at a Glance (risk-labeled) → Why This Week Matters → Risk & Compliance table → What Employees Will Notice → What Help Desk Should Expect → Cost & Licensing → Planning Horizon → If You Take No Action
- Use risk markers: 🔴 High / 🟡 Medium / 🟢 Low
- Surface relevant regulatory angles: HIPAA, SOC 2, CMMC, FedRAMP, NIST CSF, GDPR, cyber insurance

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

## Sources placement

Source URLs scraped per item are listed in the YAML front matter of each post under
a `sources:` key. The Hugo template (`layouts/_default/single.html`) renders them
as a collapsible `<details>` block at the bottom of each post — consistent placement
regardless of Claude's output structure.

---

## API cost

| Model | Est. input tokens | Est. output tokens | Est. per run (both calls) |
|---|---|---|---|
| claude-sonnet-4-6 | ~15,000–25,000 | ~3,000–4,000 | ~$0.30–1.00 |

Set a spend limit at `console.anthropic.com → Billing → Spend limits`.
A $10/month cap is sufficient for weekly runs with headroom for manual re-runs.

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
# digest.py
python digest.py                          # Generate digest + Executive's Guide from pending_draft.json
python digest.py --skip-exec              # Technical digest only (skip Executive's Guide)
python digest.py --draft path/to/file     # Use a specific draft file
python digest.py --dry-run                # Print prompt, skip API call
python digest.py --keep-pending           # Don't archive pending draft after publish

# scraper.py
python scraper.py                         # Normal run — accumulate new items
python scraper.py --force-all             # Bypass dedup — pull everything available
python scraper.py --source Intune         # Single source only
python scraper.py --health-only           # Health sources only — no draft or state changes
```
