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

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
POSTS_DIR = BASE_DIR / "site" / "content" / "posts"
ENV_FILE = Path("/opt/modern-work-weekly/.env")

POSTS_DIR.mkdir(parents=True, exist_ok=True)

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
- Front matter: title, date, description (1 punchy sentence), tags (lowercase, relevant topics), categories (from the standard list)
- Top 5 section: the 5 most important changes this week with a brief why-it-matters for each
- Title format must be exactly: "Modern Work Weekly — Week of YYYY-MM-DD"
- Per-category sections: h2 headings, bullet points per item, bold the item title, include phase tag (GA/Preview/etc)
- Action Required section: any items with deadlines or required admin steps, with dates
- End with a {{< sources >}} shortcode listing the source URLs

Standard categories: Endpoint Management, Identity & Access, Security & Compliance, Collaboration & Productivity, Automation & AI

Tone: confident, peer-to-peer, no fluff. Write like a senior engineer briefing their team."""

DIGEST_PROMPT_TEMPLATE = """Here is this week's scraped Microsoft update data. Produce the full weekly digest.

Week of: {week_of}
Total new items: {total_new_items}
Sources checked: {sources}

RAW DATA:
{grouped_items}

Produce the complete Hugo markdown post. Start immediately with the YAML front matter (---). Do not add any preamble or explanation outside the markdown."""


def find_latest_draft() -> Path:
    drafts = sorted(STATE_DIR.glob("weekly_draft_*.json"), reverse=True)
    if not drafts:
        log.error("No weekly draft found in state/. Run scraper.py first.")
        sys.exit(1)
    return drafts[0]


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

    print(f"\n{'='*60}")
    print(f"  Digest drafted: {post_path}")
    print(f"  Next step:      Review the post, edit as needed, then:")
    print(f"                  git add . && git commit -m 'digest: {week_of}' && git push")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Modern Work Weekly — Claude API digest drafter")
    parser.add_argument("--draft", type=str, default=None,
                        help="Path to a specific weekly_draft_*.json (default: latest)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the prompt without calling the API")
    args = parser.parse_args()
    run(args)
