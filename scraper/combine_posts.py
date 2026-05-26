#!/usr/bin/env python3
"""
combine_posts.py - Merge two digest posts into one and regenerate both tech and exec versions.

Usage:
    python combine_posts.py --into 2026-05-19 --absorb 2026-05-18

This will:
  1. Read both post files
  2. Send combined content to Claude to produce a single merged digest
  3. Write the merged digest to the --into date
  4. Generate an exec guide from the merged digest
  5. Delete the --absorb post and its exec counterpart
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
EXEC_DIR  = BASE_DIR / "site" / "content" / "exec"
ENV_FILE  = Path("/opt/modern-work-weekly/.env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)

DIGEST_SYSTEM_PROMPT = """You are an expert Microsoft 365 technical writer producing a weekly digest for Modern Work Engineers.

Your output must be valid Hugo-flavored Markdown with YAML front matter. Be direct, technical, and opinionated.

Format rules:
- Front matter: title (exactly "Modern Work Weekly — Week of YYYY-MM-DD"), date, description (1-2 punchy sentences), tags, categories, sources (YAML list of all source URLs from both input posts)
- Do NOT write an intro paragraph in the post body. Start directly with the first section heading.
- Top 5 section: the 5 most important changes across both weeks combined
- Per-category sections with h2 headings ONLY (Identity, Devices, Apps, Data, Network, Visibility & Automation). One bullet per item:
  - **[Title](source-url)** `Phase` — 1-3 sentences on practical impact.
  Link each title to its source URL where available.
- Section order: Top 5 → category sections → Action Required → end
- Action Required section: items with deadlines or required admin steps, deadline date called out prominently
- Deduplicate: if both source posts cover the same item, include it once (best version)

Tags: lowercase-hyphenated from: intune, entra-id, defender-xdr, defender-for-endpoint, defender-for-office-365, windows-autopatch, autopilot, windows-365, purview, teams, sharepoint, onedrive, exchange, copilot, copilot-studio, zero-trust, modern-work, identity, endpoint-management, conditional-access, global-secure-access, viva, windows, teams-rooms, data-lifecycle, shadow-ai, dspm, hotpatch, power-platform

Categories: Identity, Devices, Apps, Data, Network, Visibility & Automation

Tone: confident, peer-to-peer, no fluff."""

EXEC_SYSTEM_PROMPT = """You are a trusted technology advisor writing a weekly briefing for C-suite executives, IT directors, compliance officers, and business leaders at organizations using Microsoft 365.

Your audience makes decisions about risk, budget, compliance, and people. They do not configure technology. Write accordingly.

Your output must be valid Hugo-flavored Markdown with YAML front matter.

Risk levels:
🔴 High — act now or face measurable business, financial, or compliance risk
🟡 Medium — plan within 30 days; budget or approval may be needed
🟢 Low — awareness only; no immediate action required

Format rules:
- Front matter: title (exactly "Executive's Guide — Week of YYYY-MM-DD"), date, description, categories: ["Executive Guide"], tags (business-level)
- ## The Week at a Glance — 3-4 risk-labeled bullets in plain English
- ## Why This Week Matters — 2-3 sentences; the one thing leadership must understand
- ## Risk & Compliance — table: Change | Business Risk | Regulatory Angle | Act By
- ## What Your Employees Will Notice — user-facing changes to communicate proactively
- ## What Your Help Desk Should Expect — ticket types or support volume changes
- ## Cost & Licensing — licensing implications (omit if nothing applies)
- ## Planning Horizon — deadlines in 30/60/90 days requiring leadership decisions
- ## If You Take No Action — consequences for the 2-3 highest-risk items only

Source citations at end of each section (except Week at a Glance):
  *Sources: [Descriptive Name](url) · [Descriptive Name](url)*
Use named references: "Microsoft Threat Intelligence", "Entra What's New", "Intune What's New", etc.

Regulatory angles: HIPAA, SOC 2, CMMC, FedRAMP, NIST CSF, cyber insurance, GDPR, state privacy laws.

Tone: trusted advisor, calm, factual, direct. Like a Friday briefing from your CISO to the board."""


def read_post(date: str) -> str:
    path = POSTS_DIR / f"{date}.md"
    if not path.exists():
        log.error(f"Post not found: {path}")
        sys.exit(1)
    return path.read_text(encoding="utf-8")


def call_claude(system: str, user: str, max_tokens: int = 4096) -> str:
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text


def run(args):
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
    else:
        load_dotenv()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    into_date   = args.into
    absorb_date = args.absorb

    log.info(f"Reading posts: {absorb_date} + {into_date}")
    post_a = read_post(absorb_date)
    post_b = read_post(into_date)

    # ── Step 1: Generate merged technical digest ──────────────────────────
    log.info("Generating merged technical digest...")
    merged_prompt = (
        f"Merge these two digest posts into a single digest for the week of {into_date}. "
        f"Deduplicate items that appear in both. Combine the best content from each.\n\n"
        f"Digest URL: https://modernworkweekly.com/posts/{into_date}/\n\n"
        f"=== POST 1 (week of {absorb_date}) ===\n{post_a}\n\n"
        f"=== POST 2 (week of {into_date}) ===\n{post_b}\n\n"
        f"Start immediately with YAML front matter (---). Do not wrap in code fences."
    )
    merged_content = call_claude(DIGEST_SYSTEM_PROMPT, merged_prompt)

    # Write merged digest (back up existing first)
    into_path = POSTS_DIR / f"{into_date}.md"
    if into_path.exists():
        into_path.rename(into_path.with_suffix(".md.bak"))
        log.info(f"Backed up existing {into_date}.md")
    into_path.write_text(merged_content, encoding="utf-8")
    log.info(f"Merged digest written → {into_path}")

    # ── Step 2: Generate exec guide from merged digest ────────────────────
    log.info("Generating exec guide from merged digest...")
    exec_prompt = (
        f"Here is the merged technical digest for the week of {into_date}. "
        f"Produce the Executive's Guide briefing.\n\n"
        f"Digest URL: https://modernworkweekly.com/posts/{into_date}/\n\n"
        f"DIGEST CONTENT:\n{merged_content}\n\n"
        f"Start immediately with YAML front matter (---). Do not wrap in code fences."
    )
    exec_content = call_claude(EXEC_SYSTEM_PROMPT, exec_prompt)

    exec_path = EXEC_DIR / f"{into_date}.md"
    if exec_path.exists():
        exec_path.rename(exec_path.with_suffix(".md.bak"))
        log.info(f"Backed up existing exec/{into_date}.md")
    exec_path.write_text(exec_content, encoding="utf-8")
    log.info(f"Exec guide written → {exec_path}")

    # ── Step 3: Remove absorbed post and its exec counterpart ─────────────
    absorb_post = POSTS_DIR / f"{absorb_date}.md"
    absorb_exec = EXEC_DIR  / f"{absorb_date}.md"

    for path in [absorb_post, absorb_exec]:
        if path.exists():
            path.unlink()
            log.info(f"Deleted {path}")

    print(f"\n{'='*60}")
    print(f"  Merged digest:  {into_path}")
    print(f"  Exec guide:     {exec_path}")
    print(f"  Deleted:        posts/{absorb_date}.md + exec/{absorb_date}.md")
    print(f"\n  Review, then commit:")
    print(f"  git add site/content/ && git commit -m 'refactor: merge {absorb_date} into {into_date}' && git push origin main")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge two digest posts into one")
    parser.add_argument("--into",   required=True, help="Date to keep (YYYY-MM-DD)")
    parser.add_argument("--absorb", required=True, help="Date to absorb and delete (YYYY-MM-DD)")
    run(parser.parse_args())
