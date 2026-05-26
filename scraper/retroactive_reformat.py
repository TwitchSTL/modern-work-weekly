#!/usr/bin/env python3
"""
retroactive_reformat.py - Reformat existing digest posts to match the current style guide.

Reads an existing post, sends it to Claude with the current SYSTEM_PROMPT and an
explicit reformat instruction, then writes the result back (backing up the original).

Fixes:
  - Converts h3-heading format to bullet format with clickable titles
  - Moves Action Required to 2nd-to-last position (before Sources)
  - Moves source URLs to YAML front matter (removes {{< sources >}} shortcode)
  - Removes non-standard sections (Graph/API hooks, etc.)
  - Deduplicates sources already cited inline

Usage:
    python retroactive_reformat.py --date 2026-05-17
    python retroactive_reformat.py --date 2026-05-26
    python retroactive_reformat.py --date 2026-05-17 --dry-run
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

BASE_DIR  = Path(__file__).resolve().parent.parent
POSTS_DIR = BASE_DIR / "site" / "content" / "posts"
ENV_FILE  = Path("/opt/modern-work-weekly/.env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Microsoft 365 technical writer producing a weekly digest for Modern Work Engineers — the people responsible for designing, deploying, and securing M365 environments.

Your output must be valid Hugo-flavored Markdown with YAML front matter. Be direct, technical, and opinionated. Engineers read this to know what actually matters this week and what they need to do about it. Cut marketing language. Surface deadlines, breaking changes, and admin actions prominently.

Format rules:
- Front matter: title, date, description (1-2 punchy sentences matching the week's actual tone — highlight what's most notable whether that's a new feature, a deadline, a risk, or a capability unlock; not everything is a warning, some weeks are rich with feature enablements or reporting improvements), tags (see standard list below), categories (from the standard list)
- Do NOT write an intro paragraph in the post body. The front matter description already serves that purpose and is rendered separately by the site template. Start the body directly with the first section heading.
- Top 5 section: the 5 most important changes this week with a brief why-it-matters for each
- Title format must be exactly: "Modern Work Weekly — Week of YYYY-MM-DD"
- Per-category sections: h2 headings ONLY — never use h3 or h4 inside category sections. One bullet point per item, exactly this format:
  `- **[Title](source-url)** [phase tag] — [1-3 sentences: lead with the practical implication for the engineer's environment, then what changed, then what to watch or do. Read like a senior engineer's key note, not a product description.]`
  Link each title to its source URL using Markdown link syntax. If no URL is available, write the title without a link.
- Section order must be: Top 5 -> pillar category sections (Identity, Devices, Apps, Data, Network, Visibility & Automation) -> Action Required -> sources front matter. Do NOT place Action Required before the category sections.
- Action Required section: any items with deadlines or required admin steps, with dates. Use the same bullet format as category sections, with the deadline date called out prominently at the start of the description.
- List all source URLs in the YAML front matter under a `sources:` key as a YAML list. Do NOT include a {{< sources >}} shortcode or Sources section in the post body.
- Do NOT include a "Graph / API / automation hooks" section or similar non-standard sections.

Tags must use lowercase-hyphenated format. Use only from this standard set (pick what applies):
intune, entra-id, defender-xdr, defender-for-endpoint, defender-for-office-365,
windows-autopatch, autopilot, windows-365, purview, teams, sharepoint, onedrive,
exchange, copilot, copilot-studio, zero-trust, modern-work, identity,
endpoint-management, conditional-access, global-secure-access, viva, windows,
teams-rooms, data-lifecycle, shadow-ai, dspm, hotpatch, power-platform

Categories align to Microsoft Zero Trust pillars - use exactly these names:
Identity, Devices, Apps, Data, Network, Visibility & Automation

Tone: confident, peer-to-peer, no fluff. Write like a senior engineer briefing their team."""


def reformat_post(date: str, dry_run: bool = False) -> None:
    post_path = POSTS_DIR / f"{date}.md"
    if not post_path.exists():
        log.error(f"Post not found: {post_path}")
        sys.exit(1)

    original = post_path.read_text(encoding="utf-8")
    log.info(f"Read {len(original)} chars from {post_path.name}")

    user_prompt = (
        f"Reformat the following digest post for the week of {date} to exactly match the current style guide. "
        f"IMPORTANT: Preserve all content — every item, fact, deadline, and source URL must be kept. "
        f"What to fix:\n"
        f"  1. Convert any h3-heading format to the bullet format: - **[Title](url)** [phase] -- description\n"
        f"  2. Move Action Required to the 2nd-to-last position, after all category sections\n"
        f"  3. Move all source URLs to YAML front matter as a 'sources:' list — remove any {{{{< sources >}}}} shortcode\n"
        f"  4. Remove non-standard sections (Graph/API hooks, etc.) — inline any useful content into the relevant category section\n"
        f"  5. For items that don't have a specific source URL, link to the most relevant official Microsoft docs URL you can infer from context, or omit the link\n"
        f"  6. Keep the title, date, description, tags, and categories (may add/adjust tags if appropriate)\n\n"
        f"Digest URL: https://modernworkweekly.com/posts/{date}/\n\n"
        f"ORIGINAL POST:\n{original}\n\n"
        f"Start immediately with YAML front matter (---). Do not wrap in code fences. Do not add preamble."
    )

    if dry_run:
        print("=== DRY RUN — prompt that would be sent ===")
        print(user_prompt[:2000], "...[truncated]")
        return

    log.info("Calling Claude API...")
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    result = message.content[0].text
    log.info(f"Received {len(result)} chars from Claude")

    # Back up original
    backup = post_path.with_suffix(".md.bak")
    post_path.rename(backup)
    log.info(f"Original backed up -> {backup.name}")

    post_path.write_text(result, encoding="utf-8")
    log.info(f"Reformatted post written -> {post_path}")

    print(f"\n{'='*60}")
    print(f"  Reformatted: {post_path}")
    print(f"  Backup:      {backup}")
    print(f"\n  Review, then commit:")
    print(f"  git add site/content/posts/{date}.md && git commit -m 'refactor: reformat {date} digest' && git push origin main")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reformat an existing digest post to the current style guide")
    parser.add_argument("--date",    required=True, help="Post date to reformat (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Show prompt without calling API")
    args = parser.parse_args()

    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
    else:
        load_dotenv()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    reformat_post(args.date, dry_run=args.dry_run)
