#!/usr/bin/env python3
"""
digest.py — Phase 2 auto-drafting via Claude API.

Reads the latest weekly_draft_*.json, sends it to Claude with the master
prompt, and writes a ready-to-review Hugo markdown file to site/content/posts/.

Usage:
    python digest.py                        # Use latest draft
    python digest.py --draft state/weekly_draft_2026-05-17.json
    python digest.py --dry-run              # Print prompt only, no API call

Requires ANTHROPIC_API_KEY in /opt/modern-work-weekly/.env or environment.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv
import generate_search_index

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
POSTS_DIR = BASE_DIR / "site" / "content" / "posts"
EXEC_POSTS_DIR = BASE_DIR / "site" / "content" / "exec"
ENV_FILE = Path("/opt/modern-work-weekly/.env")
PENDING_DRAFT_FILE = STATE_DIR / "pending_draft.json"
ARCHIVE_DIR = STATE_DIR / "archive"
HEALTH_DATA_FILE = BASE_DIR / "site" / "data" / "health.json"
HEALTH_BASELINE_FILE = STATE_DIR / "health_baseline.json"

POSTS_DIR.mkdir(parents=True, exist_ok=True)
EXEC_POSTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ── Master prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert Microsoft 365 technical writer producing a weekly digest for Modern Work Engineers — the people responsible for designing, deploying, and securing M365 environments.

Your output must be valid Hugo-flavored Markdown with YAML front matter. Be direct, technical, and opinionated. Engineers read this to know what actually matters this week and what they need to do about it. Cut marketing language. Surface deadlines, breaking changes, and admin actions prominently.

Format rules:
- Front matter: title, date, description (1-2 punchy sentences matching the week's actual tone — highlight what's most notable whether that's a new feature, a deadline, a risk, or a capability unlock; not everything is a warning, some weeks are rich with feature enablements or reporting improvements), tags (see standard list below), categories (from the standard list)
- Do NOT write an intro paragraph in the post body. The front matter description already serves that purpose and is rendered separately by the site template. Start the body directly with the first section heading.
- Top 5 section: the 5 most important changes this week with a brief why-it-matters for each
- Title format must be exactly: "Modern Work Weekly — Week of YYYY-MM-DD"
- Per-category sections: h2 headings ONLY — never use h3 or h4 inside category sections. One bullet point per item, exactly this format:
  `- **[Title](source-url)** [phase tag] — [1–3 sentences: lead with the practical implication for the engineer's environment, then what changed, then what to watch or do. Read like a senior engineer's key note, not a product description.]`
  Link each title to its source URL from the raw data using Markdown link syntax. If no URL is available for an item, write the title without a link.
- Section order must be: Top 5 → pillar category sections (Identity, Devices, Apps, Data, Network, Visibility & Automation) → Action Required → sources front matter. Do NOT place Action Required before the category sections.
- Action Required section: any items with deadlines or required admin steps, with dates. Use the same bullet format as category sections, with the deadline date called out prominently at the start of the description.
- List all source URLs in the YAML front matter under a `sources:` key as a YAML list. Do NOT include a {{< sources >}} shortcode in the post body.

Tags must use lowercase-hyphenated format. Use only from this standard set (pick what applies):
intune, entra-id, defender-xdr, defender-for-endpoint, defender-for-office-365,
windows-autopatch, autopilot, windows-365, purview, teams, sharepoint, onedrive,
exchange, copilot, copilot-studio, zero-trust, modern-work, identity,
endpoint-management, conditional-access, global-secure-access, viva, windows,
teams-rooms, data-lifecycle, shadow-ai, dspm, hotpatch, power-platform

Categories align to Microsoft Zero Trust pillars — use exactly these names:
Identity, Devices, Apps, Data, Network, Visibility & Automation

Map content accordingly: Entra/MFA/PIM → Identity; Intune/Autopatch/MDM → Devices; Teams/SharePoint/Copilot features → Apps; Purview/DLP/Sensitivity Labels → Data; Global Secure Access/networking → Network; Defender/SIEM/Graph API/AI agents → Visibility & Automation

Tone: confident, peer-to-peer, no fluff. Write like a senior engineer briefing their team."""

EXEC_SYSTEM_PROMPT = """You are a trusted technology advisor writing a weekly briefing for C-suite executives, IT directors, compliance officers, and business leaders at organizations using Microsoft 365.

Your audience makes decisions about risk, budget, compliance, and people. They do not configure technology. Write accordingly — no unexplained jargon, no assumed technical knowledge.

Your output must be valid Hugo-flavored Markdown with YAML front matter.

Risk levels — use exactly these markers in the "Week at a Glance" section:
🔴 High — act now or face measurable business, financial, or compliance risk
🟡 Medium — plan within 30 days; budget or approval may be needed
🟢 Low — awareness only; no immediate action required

Format rules:
- Front matter: title (must be exactly "Executive's Guide — Week of YYYY-MM-DD"), date, description (1-2 sentences on the week's business significance — not technical), categories: ["Executive Guide"], tags (business-level: compliance, security, cost, user-impact, licensing, identity, devices, data-protection)
- ## The Week at a Glance — 3-4 risk-labeled bullets in plain English
- ## Why This Week Matters — 2-3 sentences of leadership-level context; the one thing leadership must understand
- ## Risk & Compliance — markdown table with columns: Change | Business Risk | Regulatory Angle | Act By
- ## What Your Employees Will Notice — bullets of user-facing changes; what to communicate proactively
- ## What Your Help Desk Should Expect — specific ticket types or support volume changes to anticipate
- ## Cost & Licensing — licensing tier implications, new costs, or spend optimization opportunities (omit section if nothing applies)
- ## Planning Horizon — deadlines in the next 30/60/90 days requiring leadership decisions, budget approval, or vendor coordination
- ## If You Take No Action — plain-language consequences for the 2-3 highest-risk items only

Regulatory angles to surface where relevant: HIPAA, SOC 2, CMMC, FedRAMP, NIST CSF, cyber insurance requirements, GDPR, state privacy laws.

Source citations — executives trust named references, not raw URLs:
- At the end of each section (except "The Week at a Glance"), include a single line formatted exactly as:
  `*Sources: [Descriptive Name](url) · [Descriptive Name](url)*`
- Use 1–3 sources per section, drawn from the raw data URLs. Name them meaningfully: "Microsoft Threat Intelligence", "Entra What's New", "M365 Roadmap", "Intune What's New", "Microsoft Security Blog", etc. Never paste a raw URL as the link text.
- Omit the Sources line if no relevant URLs are available for that section.

Tone: trusted advisor, calm, factual, direct. Not alarmist. Not dismissive. Like a Friday briefing from your CISO to the board."""

LINKEDIN_SYSTEM_PROMPT = """You write the weekly LinkedIn newsletter edition of Modern Work Weekly — a digest for Microsoft 365 engineers, architects, and admins.

Voice: peer-professional, direct, occasionally dry. No first-person "I". Speak to the reader's role — "Intune admins will want to flag this", "Security teams should note", "If your org runs hybrid identity...", "If your C-level asks about AI governance this week, here's the answer." Confident, not hype-y.

Format — plain text optimised for LinkedIn's newsletter editor (no markdown syntax, no asterisks, no backtick code blocks). Use these conventions:
- Section headers in ALL CAPS on their own line
- Emoji sparingly as visual anchors (one per section max)
- Bullet points with a dash and space: "- item"
- Blank line between every section
- Keep total length 400–600 words

Structure (in order):
1. Hook line — one punchy sentence that names the biggest story this week. No greeting, no "this week in M365". Just the hook.
2. TOP 5 THIS WEEK — the 5 most important changes, one line each. Lead with the impact, not the feature name.
3. WORTH YOUR ATTENTION — 2–3 items that aren't urgent but signal where things are heading. One sentence each.
4. ONE FOR THE HELP DESK (optional) — a single change that's going to generate tickets or questions. Skip if nothing fits.
5. Closing line — one sentence pointing to the full digest. Format: "Full digest with sources and admin actions: [URL]"

Do not include hashtags, emojis in the closing line, or a sign-off. Do not wrap output in code fences."""

LINKEDIN_PROMPT_TEMPLATE = """Here is the week's digest content. Produce the LinkedIn newsletter edition.

Week of: {week_of}
Digest URL: https://modernworkweekly.com/posts/{week_of}/

DIGEST CONTENT (Top 5 and category items):
{digest_content}

Output plain text only. No markdown syntax. No preamble."""

EXEC_DIGEST_PROMPT_TEMPLATE = """Here is this week's Microsoft 365 update data. Produce the Executive's Guide briefing.

Week of: {week_of}
Total items: {total_new_items}

RAW DATA:
{grouped_items}

Produce the complete Hugo markdown post for executive and leadership audiences. Start immediately with YAML front matter (---). Do not wrap in code fences. Do not add preamble or explanation outside the markdown."""

DIGEST_PROMPT_TEMPLATE = """Here is this week's scraped Microsoft update data. Produce the full weekly digest.

Week of: {week_of}
Total new items: {total_new_items}
Sources checked: {sources}

RAW DATA:
{grouped_items}

Produce the complete Hugo markdown post. Start immediately with the YAML front matter (---). Do not wrap the output in code fences. Do not add any preamble or explanation outside the markdown."""


def update_health_baseline():
    """Snapshot the current health.json titles as the new baseline.

    Called after a digest is published so next week's scraper run can diff
    against these titles and mark only net-new issues as is_new=True.
    """
    if not HEALTH_DATA_FILE.exists():
        log.info("health.json not found — skipping baseline update.")
        return
    try:
        with open(HEALTH_DATA_FILE) as f:
            health = json.load(f)
        titles = [
            item["title"]
            for source in health.get("sources", [])
            for item in source.get("items", [])
        ]
        STATE_DIR.mkdir(exist_ok=True)
        with open(HEALTH_BASELINE_FILE, "w") as f:
            json.dump({"updated": health.get("updated", ""), "titles": titles}, f, indent=2)
        log.info(f"Health baseline updated — {len(titles)} titles recorded → {HEALTH_BASELINE_FILE}")
    except Exception as e:
        log.warning(f"Failed to update health baseline (non-fatal): {e}")


def find_latest_draft() -> Path:
    # Prefer the rolling pending draft — it accumulates items across all runs
    # since the last digest was published.
    if PENDING_DRAFT_FILE.exists():
        log.info("Found pending_draft.json — using accumulated rolling draft.")
        return PENDING_DRAFT_FILE
    # Fall back to the most recent per-run snapshot
    drafts = sorted(STATE_DIR.glob("weekly_draft_*.json"), reverse=True)
    if not drafts:
        log.error("No draft found in state/. Run scraper.py first.")
        sys.exit(1)
    log.info("No pending_draft.json found — falling back to latest run snapshot.")
    return drafts[0]


def archive_pending_draft(week_of: str):
    """Move pending_draft.json to state/archive/ after a successful publish.

    This clears the slate so the next scraper run starts a fresh accumulation.
    """
    if not PENDING_DRAFT_FILE.exists():
        return
    ARCHIVE_DIR.mkdir(exist_ok=True)
    archive_path = ARCHIVE_DIR / f"pending_draft_{week_of}.json"
    PENDING_DRAFT_FILE.rename(archive_path)
    log.info(f"Pending draft archived → {archive_path}")


def load_draft(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def build_prompt(draft: dict) -> str:
    # Compact the grouped items to save tokens — keep title, body, phase, admin_action
    compact = {}
    for cat, items in draft.get("grouped_items", {}).items():
        compact[cat] = [
            {
                "title": item["title"],
                "body": item["body"],
                "source": item["source"],
                "phase": item.get("phase", "GA"),
                "admin_action": item.get("admin_action"),
                "url": item.get("url", ""),
            }
            for item in items
        ]

    return DIGEST_PROMPT_TEMPLATE.format(
        week_of=draft.get("week_of", datetime.now(timezone.utc).date().isoformat()),
        total_new_items=draft.get("total_new_items", 0),
        sources=", ".join(draft.get("sources_checked", [])),
        grouped_items=json.dumps(compact, indent=2),
    )


def call_claude(prompt: str) -> str:
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment
    log.info("Calling Claude API (claude-sonnet-4-6)...")
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def build_exec_prompt(draft: dict) -> str:
    compact = {}
    for cat, items in draft.get("grouped_items", {}).items():
        compact[cat] = [
            {
                "title": item["title"],
                "body": item["body"],
                "source": item["source"],
                "phase": item.get("phase", "GA"),
                "admin_action": item.get("admin_action"),
                "url": item.get("url", ""),
            }
            for item in items
        ]
    return EXEC_DIGEST_PROMPT_TEMPLATE.format(
        week_of=draft.get("week_of", datetime.now(timezone.utc).date().isoformat()),
        total_new_items=draft.get("total_new_items", 0),
        grouped_items=json.dumps(compact, indent=2),
    )


def build_linkedin_prompt(draft: dict, week_of: str) -> str:
    """Build a compact digest summary to feed the LinkedIn draft."""
    lines = []
    for cat, items in draft.get("grouped_items", {}).items():
        lines.append(f"[{cat}]")
        for item in items:
            lines.append(f"  - {item['title']}: {(item.get('body') or '')[:200]}")
    return LINKEDIN_PROMPT_TEMPLATE.format(
        week_of=week_of,
        digest_content="\n".join(lines),
    )


def call_claude_linkedin(prompt: str) -> str:
    client = anthropic.Anthropic()
    log.info("Calling Claude API for LinkedIn newsletter draft...")
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=LINKEDIN_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def write_linkedin_draft(content: str, week_of: str) -> Path:
    path = STATE_DIR / f"linkedin_draft_{week_of}.txt"
    path.write_text(content, encoding="utf-8")
    log.info(f"LinkedIn draft written → {path}")
    return path


def call_claude_exec(prompt: str) -> str:
    client = anthropic.Anthropic()
    log.info("Calling Claude API for Executive's Guide...")
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=EXEC_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def write_exec_post(content: str, week_of: str) -> Path:
    post_path = EXEC_POSTS_DIR / f"{week_of}.md"
    if post_path.exists():
        backup = post_path.with_suffix(".md.bak")
        post_path.rename(backup)
        log.info(f"Existing exec post backed up → {backup}")
    with open(post_path, "w") as f:
        f.write(content)
    log.info(f"Exec post written → {post_path}")
    return post_path


def write_post(content: str, week_of: str) -> Path:
    post_path = POSTS_DIR / f"{week_of}.md"
    if post_path.exists():
        backup = post_path.with_suffix(".md.bak")
        post_path.rename(backup)
        log.info(f"Existing post backed up → {backup}")
    with open(post_path, "w") as f:
        f.write(content)
    log.info(f"Post written → {post_path}")
    return post_path


def run(args):
    # Load .env if present
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
        log.info(f"Loaded env from {ENV_FILE}")
    else:
        load_dotenv()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY not set. Add it to /opt/modern-work-weekly/.env")
        sys.exit(1)

    draft_path = Path(args.draft) if args.draft else find_latest_draft()
    log.info(f"Using draft: {draft_path}")

    draft = load_draft(draft_path)

    # When consuming the rolling pending draft, use today as the publish date so
    # the post filename reflects when it was actually published, not when
    # scraping started.  Per-run snapshots keep their own run_date.
    if draft_path == PENDING_DRAFT_FILE:
        week_of = datetime.now(timezone.utc).date().isoformat()
        runs = draft.get("runs", [])
        if runs:
            log.info(f"Pending draft covers {len(runs)} run(s): {', '.join(runs)}")
    else:
        week_of = draft.get("week_of", datetime.now(timezone.utc).date().isoformat())

    prompt = build_prompt(draft)

    if args.dry_run:
        print("\n" + "="*60)
        print("SYSTEM PROMPT:")
        print(SYSTEM_PROMPT)
        print("\nUSER PROMPT:")
        print(prompt[:2000] + "..." if len(prompt) > 2000 else prompt)
        print("="*60)
        log.info("Dry run complete — no API call made.")
        return

    content = call_claude(prompt)
    post_path = write_post(content, week_of)

    # Generate Executive's Guide unless skipped
    exec_post_path = None
    if not args.skip_exec:
        try:
            exec_prompt = build_exec_prompt(draft)
            exec_content = call_claude_exec(exec_prompt)
            exec_post_path = write_exec_post(exec_content, week_of)
        except Exception as e:
            log.warning(f"Executive's Guide generation failed (non-fatal): {e}")

    # Generate LinkedIn newsletter draft unless skipped
    linkedin_draft_path = None
    if not args.skip_linkedin:
        try:
            li_prompt = build_linkedin_prompt(draft, week_of)
            li_content = call_claude_linkedin(li_prompt)
            linkedin_draft_path = write_linkedin_draft(li_content, week_of)
        except Exception as e:
            log.warning(f"LinkedIn draft generation failed (non-fatal): {e}")

    # Clear the pending draft now that it's been published — next scraper run
    # starts a fresh accumulation.
    if not args.keep_pending and draft_path == PENDING_DRAFT_FILE:
        archive_pending_draft(week_of)

    # Regenerate the static search index so /search.json stays current.
    try:
        entries = generate_search_index.build_index(POSTS_DIR)
        generate_search_index.OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        import json as _json
        generate_search_index.OUTPUT_PATH.write_text(
            _json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log.info(f"Search index updated — {len(entries)} entries → {generate_search_index.OUTPUT_PATH}")
    except Exception as e:
        log.warning(f"Search index regeneration failed (non-fatal): {e}")

    # Snapshot current known issues as the new baseline so next week's scraper
    # can diff against them and mark only net-new issues in the sidebar.
    update_health_baseline()

    print(f"\n{'='*60}")
    print(f"  Digest drafted:      {post_path}")
    if exec_post_path:
        print(f"  Executive's Guide:   {exec_post_path}")
    if linkedin_draft_path:
        print(f"  LinkedIn draft:      {linkedin_draft_path}")
    print(f"  Next step:           Review posts, edit as needed, then:")
    print(f"                       git add . && git commit -m 'digest: {week_of}' && git push")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Modern Work Weekly — Claude API digest drafter")
    parser.add_argument("--draft", type=str, default=None,
                        help="Path to a specific weekly_draft_*.json (default: latest)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the prompt without calling the API")
    parser.add_argument("--keep-pending", action="store_true",
                        help="Don't archive pending_draft.json after publishing (useful for testing)")
    parser.add_argument("--skip-exec", action="store_true",
                        help="Skip Executive's Guide generation (technical digest only)")
    parser.add_argument("--skip-linkedin", action="store_true",
                        help="Skip LinkedIn newsletter draft generation")
    args = parser.parse_args()
    run(args)
