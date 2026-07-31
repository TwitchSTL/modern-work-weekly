# Pipeline Reference — Claude API & Digest Drafting

Documents the automated digest pipeline as implemented. Three Claude API calls are
made per Tuesday run — the technical digest, the Executive's Guide, and a LinkedIn
newsletter draft.

---

## How `digest.py` works

```
pending_draft.json      docs_updates.py (GitHub doc-commit
       │                 data, fetched separately per run)
       ▼                        │
  load_draft()              ← Prefers pending_draft.json; falls back to weekly_draft_*.json
       │                        │
       ├──────────────────────────┬──────────────────────────────┐
       ▼                          ▼                              ▼
  build_prompt() ◄───────┘  build_exec_prompt()            build_linkedin_prompt()
  call_claude()             call_claude_exec()             call_claude_linkedin()
  write_post()              write_exec_post()              write_linkedin_draft()
       │                          │                              │
       ▼                          ▼                              ▼
  site/content/posts/      site/content/exec/            state/linkedin_draft_
  YYYY-MM-DD.md            YYYY-MM-DD.md                 YYYY-MM-DD.txt
       │
       ▼
  archive_pending_draft()   ← Moves pending_draft.json → state/archive/pending_draft_YYYY-MM-DD.json
```

After all three drafts are written, `digest.py` also regenerates the static search
index (`generate_search_index.build_index` → `site/static/search.json`) and snapshots
the current known issues as the new health baseline (`update_health_baseline()`), so
next week's scraper can diff against it. Both the Executive's Guide and LinkedIn draft
are generated in `try`/`except` blocks — failures are logged as non-fatal and don't
block the technical digest from publishing.

Only the technical digest prompt consumes `docs_updates.py`'s GitHub doc-commit data
(for the optional "Documentation Updates" section) — the Exec Guide and LinkedIn
prompts don't receive it.

---

## Category taxonomy

Categories are Modern Work practice areas, not a security framework:
Identity & Access, Endpoint & Device Management, Collaboration & Productivity,
AI & Copilot, Employee Experience, Security & Compliance.

This replaced the original six Zero Trust pillars (Identity, Devices, Apps, Data,
Network, Visibility & Automation) on 2026-07-17 — the old categories were just
Microsoft's Zero Trust pillars renamed, which made the site structurally a
security-ops digest regardless of what actually shipped that week. `classify_item()`
in `scraper.py` does the actual per-item classification from title/body text against
`CLASSIFICATION_KEYWORDS` in `sources.py`, before anything reaches Claude; it returns
`(category, matched)` where `matched=False` means the item fell back to the default
category rather than hitting a real keyword. `write_classification_stats()` logs
per-run category counts and the fallback rate to `state/classification_stats.json` —
review with `python classification_report.py`.

Historical posts (through 2026-07-14) keep their original Zero Trust category labels;
this was a forward-only migration, not a retroactive relabel, to avoid breaking
existing links into published category sections.

Zero Trust survives in one place: the Executive's Guide uses it as an optional
strategic *lens* for identity/device/network/security items (see below), not as a
category name anywhere on the site.

---

## System prompt design

### Technical digest (`SYSTEM_PROMPT`)

Instructs Claude to:
- Output valid Hugo-flavored Markdown with YAML front matter
- Write in a direct, peer-to-peer engineering tone (no marketing language)
- Structure: front matter → Top 5 → per-category sections → Action Required
- List all source URLs in the YAML front matter under a `sources:` key (not in the post body)
- Use only the standard lowercase-hyphenated tag set
- Map content to Modern Work practice areas: Identity & Access / Endpoint & Device Management / Collaboration & Productivity / AI & Copilot / Employee Experience / Security & Compliance (taxonomy reframed 2026-07-17 from the prior six Zero Trust pillars — see "Category taxonomy" above)
- Surface deadlines, breaking changes, and admin actions prominently
- Documentation Updates section (optional, `## Documentation Updates`): include only when `docs_updates.py`'s GitHub doc-commit data has at least one substantive item this week; most raw commits are noise (typo/formatting fixes) and get filtered by Claude's judgment, not just included wholesale

### Executive's Guide (`EXEC_SYSTEM_PROMPT`)

Instructs Claude to:
- Write for C-suite, IT directors, compliance officers — no unexplained jargon
- Structure: front matter → Week at a Glance (risk-labeled) → Why This Week Matters → What Microsoft's Research Is Saying (optional) → Risk & Compliance → What Employees Will Notice → What Help Desk Should Expect → Cost & Licensing → Planning Horizon → If You Take No Action
- Use risk markers: 🔴 High / 🟡 Medium / 🟢 Low
- Surface relevant regulatory angles: HIPAA, SOC 2, CMMC, FedRAMP, NIST CSF, GDPR, cyber insurance
- Strategic framing: identity/device/network/security items may be framed in Zero Trust maturity terms (e.g. "closes an implicit-trust gap") where it helps leadership read posture. This is the only place Zero Trust appears as a framework — since the 2026-07-17 reframe it's a strategy lens scoped to this guide, not the site's category taxonomy (see "Category taxonomy" above)
- "What Microsoft's Research Is Saying" only appears when Viva/WorkLab "Research & Trends" items exist that week — these are routed away from the technical digest entirely and fed only to this guide, with a 30-day freshness window instead of the standard 7

### LinkedIn newsletter draft (`LINKEDIN_SYSTEM_PROMPT`)

Instructs Claude to:
- Write the weekly LinkedIn newsletter edition — peer-professional, direct, occasionally dry, speaking to the reader's role (e.g. "Intune admins will want to flag this")
- Output plain text optimized for LinkedIn's newsletter editor — no markdown syntax, no asterisks, no code blocks
- Use ALL-CAPS section headers, sparing emoji as visual anchors, dash-style bullets, and a blank line between sections
- Draft is written to `state/linkedin_draft_YYYY-MM-DD.txt` (not committed to the repo or published automatically — it's a manual-post starting point); see `linkedin/template.md` and `linkedin/formatter.py` for the article-format reference and formatting helper

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

| Call | max_tokens | Est. input tokens | Est. output tokens |
|---|---|---|---|
| Technical digest (`call_claude`) | 16,000 | ~15,000–25,000 | ~3,000–4,000 |
| Executive's Guide (`call_claude_exec`) | 8,192 | ~15,000–25,000 | ~2,000–3,000 |
| LinkedIn draft (`call_claude_linkedin`) | 1,024 | ~2,000–4,000 | ~400–800 |

All three calls together run ~$0.30–1.00 per Tuesday run on `claude-sonnet-4-6`.

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
python digest.py                          # Generate digest + Executive's Guide + LinkedIn draft from pending_draft.json
python digest.py --skip-exec              # Skip Executive's Guide generation
python digest.py --skip-linkedin          # Skip LinkedIn newsletter draft generation
python digest.py --draft path/to/file     # Use a specific draft file
python digest.py --dry-run                # Print prompt, skip API call
python digest.py --keep-pending           # Don't archive pending draft after publish

# scraper.py
python scraper.py                         # Normal run — accumulate new items
python scraper.py --force-all             # Bypass dedup — pull everything available
python scraper.py --source Intune         # Single source only
python scraper.py --health-only           # Health sources only — no draft or state changes

# docs_updates.py — GitHub doc-commit data feeding the technical digest's optional
# "Documentation Updates" section (see project_mww_github_docs_repo_mapping memory
# for why only entra-docs/memdocs/microsoft-365-docs/defender-docs are wired up)
python docs_updates.py --dry-run          # Print what would be fetched, no filtering detail
python docs_updates.py                    # Print full JSON to stdout

# classification_report.py — review category-classification stats from the last run
python classification_report.py          # Reads state/classification_stats.json
```
