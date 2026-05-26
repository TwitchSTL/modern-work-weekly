#!/usr/bin/env python3
"""
retroactive_exec.py - Generate missing Executive's Guide posts from existing digests.

Reads each post in site/content/posts/ that doesn't have a matching exec post,
sends the content to Claude with the exec system prompt, and writes the result
to site/content/exec/.

Usage:
    python retroactive_exec.py              # Generate all missing exec posts
    python retroactive_exec.py --dry-run   # List what would be generated
    python retroactive_exec.py --date 2026-05-17  # Single post only
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
POSTS_DIR = BASE_DIR / "site" / "content" / "posts"
EXEC_DIR  = BASE_DIR / "site" / "content" / "exec"
ENV_FILE  = Path("/opt/modern-work-weekly/.env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)

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

Source citations — executives trust named references, not raw URLs:
- At the end of each section (except "The Week at a Glance"), include a single line formatted exactly as:
  *Sources: [Descriptive Name](url) · [Descriptive Name](url)*
- Use 1–3 sources per section. Name them meaningfully: "Microsoft Threat Intelligence", "Entra What's New", "M365 Roadmap", "Intune What's New", "Microsoft Security Blog", etc. Never paste a raw URL as the link text.
- Omit the Sources line if no relevant URLs are available for that section.

Regulatory angles to surface where relevant: HIPAA, SOC 2, CMMC, FedRAMP, NIST CSF, cyber insurance requirements, GDPR, state privacy laws.

Tone: trusted advisor, calm, factual, direct. Not alarmist. Not dismissive. Like a Friday briefing from your CISO to the board."""


SKIP_DATES = {
    "2026-05-10",  # Welcome/intro post — not a digest, no exec guide needed
}

def get_missing_exec_dates() -> list[str]:
    """Return dates that have a digest post but no exec post."""
    post_dates = {p.stem for p in POSTS_DIR.glob("????-??-??.md")}
    exec_dates = {p.stem for p in EXEC_DIR.glob("????-??-??.md")}
    missing = sorted((post_dates - exec_dates) - SKIP_DATES)
    return missing


def generate_exec(post_path: Path) -> str:
    content = post_path.read_text(encoding="utf-8")
    date = post_path.stem

    client = anthropic.Anthropic()
    log.info(f"Calling Claude for exec guide: {date}")
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=EXEC_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"Here is the technical digest for the week of {date}. "
                f"Produce the Executive's Guide briefing based on its content.\n\n"
                f"Digest URL for reference: https://modernworkweekly.com/posts/{date}/\n\n"
                f"DIGEST CONTENT:\n{content}\n\n"
                f"Start immediately with YAML front matter (---). "
                f"Do not wrap in code fences. Do not add preamble."
            )
        }]
    )
    return message.content[0].text


def write_exec(content: str, date: str) -> Path:
    EXEC_DIR.mkdir(parents=True, exist_ok=True)
    out = EXEC_DIR / f"{date}.md"
    if out.exists():
        backup = out.with_suffix(".md.bak")
        out.rename(backup)
        log.info(f"Existing exec post backed up → {backup}")
    out.write_text(content, encoding="utf-8")
    log.info(f"Exec post written → {out}")
    return out


def run(args):
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
    else:
        load_dotenv()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    if args.date:
        dates = [args.date]
    else:
        dates = get_missing_exec_dates()

    if not dates:
        log.info("No missing exec posts found — all digests already have an exec guide.")
        return

    log.info(f"Exec posts to generate: {', '.join(dates)}")

    if args.dry_run:
        for d in dates:
            print(f"  Would generate: site/content/exec/{d}.md")
        return

    written = []
    for date in dates:
        post_path = POSTS_DIR / f"{date}.md"
        if not post_path.exists():
            log.warning(f"No post found for {date} — skipping.")
            continue
        try:
            content = generate_exec(post_path)
            path = write_exec(content, date)
            written.append(path)
        except Exception as e:
            log.error(f"Failed for {date}: {e}")

    print(f"\n{'='*60}")
    for p in written:
        print(f"  Generated: {p}")
    print(f"\n  Review, then commit:")
    print(f"  git add site/content/exec/ && git commit -m 'feat: retroactive exec guides' && git push origin main")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate missing Executive's Guide posts")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated without calling API")
    parser.add_argument("--date", type=str, default=None, help="Generate exec for a specific date only (YYYY-MM-DD)")
    run(parser.parse_args())
