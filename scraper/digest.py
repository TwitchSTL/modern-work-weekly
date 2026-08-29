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
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv
import generate_search_index
from dateutils import parse_item_date, item_age_days
from sources import EMPHASIS_KEYWORDS, EMPHASIS_TAGS

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
EMPHASIS_STATS_FILE = STATE_DIR / "emphasis_stats.json"
EMPHASIS_STATS_HISTORY_LIMIT = 20

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
- Top 5 section: heading must be exactly "## Top 5" (not "## Top 5 This Week" or any other variant — the LinkedIn draft pipeline's extract_top5() parses this heading verbatim and silently returns nothing on a mismatch). The 5 most important changes this week with a brief why-it-matters for each.
- Top 5 and CVE items: do not name-check a routine CVE (acknowledgment update, build-number correction, or any CVE whose provided cve_severity is not "Critical" and whose cve_exploited is not "Yes") in the Top 5. Only a CVE that is Critical severity or has cve_exploited: "Yes" belongs in Top 5. Every CVE, regardless of severity, still gets its own bullet in the Action Required section — see that section's rule below.
- Title format must be exactly: "Modern Work Weekly - Week of YYYY-MM-DD" (plain hyphen, not an em dash — see clean_dashes())
- Per-category sections: h2 headings ONLY — never use h3 or h4 inside category sections. One bullet point per item, exactly this format:
  `- **[Title](source-url)** [phase tag] {{< emphasis "Tag" >}} — [1–3 sentences: lead with the practical implication for the engineer's environment, then what changed, then what to watch or do. Read like a senior engineer's key note, not a product description.]`
  Link each title to its source URL from the raw data using Markdown link syntax. If no URL is available for an item, write the title without a link.
- Emphasis tags (the `{{< emphasis "..." >}}` shortcode above): OPTIONAL, added 2026-08-29, forward-only — only on new items, never inserted into historical content. This is separate from the item's category (which decides what section it lives under) and flags when an item's real substance is best understood through a different lens than its category implies. Use zero, one, or two tags from exactly this list: Identity, Endpoints, Data, Apps, Infrastructure, Network, SecOps, AI — Microsoft's own Zero Trust technology pillar names, not invented terms. Omit the shortcode entirely when an item's category already fully captures what it's about (this should be the common case — most items need no emphasis tag at all). Add one only when there's a genuine, specific reason: e.g. a Copilot item that is substantively about data loss prevention gets {{< emphasis "Data" >}} even though its category is AI & Copilot, because Microsoft's own Purview product team treats Copilot DLP as a Data Security concern (a distinct "Purview Data Security AI Admin" role exists for exactly this). Do not tag an item with the same concept its category already names (e.g. don't tag a Security & Compliance item "SecOps" just because it's security-flavored — that's not adding information). If genuinely undecided, leave the tag off; a missing tag costs nothing, a wrong one is noise.
- Section order must be: Top 5 → pillar category sections (Identity & Access, Endpoint & Device Management, Collaboration & Productivity, AI & Copilot, Employee Experience, Security & Compliance) → Action Required → Documentation Updates → sources front matter. Do NOT place Action Required before the category sections.
- Action Required section: ALWAYS include this section — never omit it. This section is a COMPLETE list, not a curated highlight reel: include EVERY CVE item provided in the data (no exceptions, regardless of severity), plus any non-CVE items with deadlines, required admin steps, governance decisions, or deprecation timelines. Use the same bullet format as category sections. For each CVE bullet, prominently lead with its severity and CVSS base score from the provided cve_severity/cve_base_score fields (e.g. "**Important · CVSS 8.0**") — if cve_severity is null for an item, write "Severity: not yet rated by MSRC" rather than inventing a rating — followed by "Surfaced in the [Week of date] digest." using the exact "Week of:" date given in the DIGEST CONTENT below (do not use any other date for this), then the same practical 1-3 sentence explanation used elsewhere. For non-CVE Action Required items, lead with the deadline date or urgency as before. If there are genuinely zero CVEs and zero other time-sensitive items this week, include the 2-3 items that most warrant an engineer's attention in the next 30 days instead.
- Documentation Updates section (## Documentation Updates): OPTIONAL — include only when the raw GitHub doc commit data has at least one substantive item; omit the entire section, heading included, if none qualify this week. This data is raw commits to Microsoft's documentation repos, and most commits are NOT worth surfacing: typo fixes, formatting passes, screenshot swaps, minor rewording, and editorial cleanup are all noise. Select only commits that represent a real content change an engineer would want to know about: a newly documented capability or setting, a changed default or behavior, an added or removed prerequisite, a retirement or deprecation notice, a corrected or clarified admin procedure, or a meaningfully rewritten guidance page. It is normal and expected for this section to be short or entirely absent most weeks; do not pad it with marginal commits to make it look substantial. Sub-group selected items under a bold pillar name on its own line (e.g. `**Identity & Access**`), then one bullet per item below it, in this format: `- **[Your own clear, engineer-facing title](commit-url)** — [1 sentence: what actually changed in the docs and why it matters].` Write your own title describing the actual change; do NOT reuse the raw commit message as the title, since commit messages are written for other doc authors, not engineers, and are often unclear standing alone.
- List all source URLs in the YAML front matter under a `sources:` key as a YAML list. Do NOT include a {{< sources >}} shortcode in the post body.
- Category sections must include EVERY item provided for that category in the input data. Do not selectively cover only some items and silently drop the rest — every item in the data has already been filtered for relevance and freshness upstream before it ever reaches you, so there is no such thing as a provided item that isn't worth including. A category with 7 items provided must produce 7 bullets, not your own trimmed-down selection of 5. This applies regardless of category size; do not artificially cap any section at a round number.

Tags must use lowercase-hyphenated format. Use only from this standard set (pick what applies):
intune, entra-id, defender-xdr, defender-for-endpoint, defender-for-office-365,
windows-autopatch, autopilot, windows-365, purview, teams, sharepoint, onedrive,
exchange, copilot, copilot-studio, zero-trust, modern-work, identity,
endpoint-management, conditional-access, global-secure-access, viva, windows,
teams-rooms, data-lifecycle, shadow-ai, dspm, hotpatch, power-platform

Categories align to Modern Work practice areas — use exactly these names:
Identity & Access, Endpoint & Device Management, Collaboration & Productivity, AI & Copilot, Employee Experience, Security & Compliance

Map content accordingly: Entra/MFA/PIM → Identity & Access; Intune/Autopatch/MDM → Endpoint & Device Management; Teams/SharePoint/OneDrive/Exchange → Collaboration & Productivity; Microsoft 365 Copilot/Copilot Studio/Agent 365/Power Platform → AI & Copilot; Viva/employee engagement or wellbeing content → Employee Experience; Purview/DLP/Defender/Global Secure Access/SIEM/Graph API → Security & Compliance

Tone: confident, peer-to-peer, no fluff. Write like a senior engineer briefing their team.

Style: Never use em dashes. Use a comma, a colon, a semicolon, or split into two separate sentences instead. Also avoid the contrastive construction "X isn't Y, it's Z" and its variants ("This isn't..., it's...", "That isn't..., it's..."); state the point directly instead of setting up a false contrast first.

Language: American English throughout. Use American spellings — "organization" not "organisation", "behavior" not "behaviour", "license" not "licence", "customize" not "customise", etc."""

EXEC_SYSTEM_PROMPT = """You are a trusted technology advisor writing a weekly briefing for C-suite executives, IT directors, compliance officers, and business leaders at organizations using Microsoft 365.

Your audience makes decisions about risk, budget, compliance, and people. They do not configure technology. Write accordingly — no unexplained jargon, no assumed technical knowledge.

Your output must be valid Hugo-flavored Markdown with YAML front matter.

Risk levels — use exactly these markers in the "Week at a Glance" section:
🔴 High — act now or face measurable business, financial, or compliance risk
🟡 Medium — plan within 30 days; budget or approval may be needed
🟢 Low — awareness only; no immediate action required

Format rules:
- Front matter: title (must be exactly "Executive's Guide - Week of YYYY-MM-DD", plain hyphen), date, description (1-2 sentences on the week's business significance — not technical), categories: ["Executive Guide"], tags (business-level: compliance, security, cost, user-impact, licensing, identity, devices, data-protection)
- ## The Week at a Glance — 3-4 risk-labeled bullets in plain English. If any 🔴 High item exists this week, it must be the FIRST bullet listed (the site lifts this exact bullet into a hero alert above the fold, so its bold title must stand alone as a clear, punchy headline of what's wrong and its sentence must make sense read in isolation, without depending on the bullets around it).
- ## Why This Week Matters — 2-3 sentences of leadership-level context; the one thing leadership must understand
- ## What Microsoft's Research Is Saying — OPTIONAL. Include only when "Research & Trends" items are present in the raw data; omit the entire section, heading included, if there are none this week. 1-3 bullets translating Microsoft's own workplace/AI research (Viva/WorkLab research essays) into what it means for this organization's planning. This is context, not an action item, so do not add it to Risk & Compliance or Planning Horizon.
- ## Risk & Compliance — a bulleted list, one item per bullet, in the same scannable style as "The Week at a Glance": risk emoji (🔴/🟡/🟢) + bold linked item title, then a colon and ONE punchy sentence covering the business risk. Fold the regulatory angle and act-by date into a short trailing clause in that same sentence, or a brief second sentence if needed. Do not use a markdown table for this section. Example: "🔴 **[ACR Stealer credential campaign](url):** Active attacks are stealing browser credentials, risking account takeover; relevant to SOC 2 and HIPAA, act immediately."
- ## What Your Employees Will Notice — bullets of user-facing changes; what to communicate proactively
- ## What Your Help Desk Should Expect — specific ticket types or support volume changes to anticipate
- ## Cost & Licensing — licensing tier implications, new costs, or spend optimization opportunities (omit section if nothing applies)
- ## Planning Horizon — a bulleted list grouped by urgency, one item per bullet: bold the timeframe first (e.g. "**Within 30 days:**"), then the bold linked item title, then a colon and ONE short sentence naming the decision, budget approval, or vendor coordination required. Do not use a markdown table for this section. Example: "**Within 30 days — [Passkeys as default authentication](url):** Plan employee communication and help desk readiness before rollout reaches your workforce."
- ## If You Take No Action — plain-language consequences for the 2-3 highest-risk items only

Regulatory angles to surface where relevant: HIPAA, SOC 2, CMMC, FedRAMP, NIST CSF, cyber insurance requirements, GDPR, state privacy laws.

Strategic framing: when a change affects identity, device, or network access controls, frame its significance in Zero Trust maturity terms where it helps leadership understand posture, e.g. "closes an implicit-trust gap," "strengthens least-privilege enforcement," "extends verification to a previously trusted zone." This is a strategy lens for identity/device/network/security items specifically, used where it adds insight, not a label to attach to every row. Collaboration, AI/Copilot, and employee-experience items don't need it.

Content-emphasis tags: OPTIONAL, added 2026-08-29, forward-only. In Risk & Compliance and Planning Horizon bullets only, when an item's real substance sits under a different Zero Trust pillar than its section implies (e.g. a Copilot item that's really a data-loss-prevention story), you may add `{{< emphasis "Tag" >}}` right after the bolded linked title, using one or two of exactly: Identity, Endpoints, Data, Apps, Infrastructure, Network, SecOps, AI. This is invisible to the reader (rendered as a hidden marker for the site's cross-linking, not printed text) so it never disrupts the prose. Omit it entirely in the common case where the section already makes the item's nature clear.

Source citations — REQUIRED. Executives trust named references, not raw URLs:
- At the end of EVERY section (including Risk & Compliance, Planning Horizon, and If You Take No Action), you MUST include a line formatted exactly as:
  `*Sources: [Descriptive Name](url) · [Descriptive Name](url)*`
- Use 1–3 sources per section, drawn from the raw data URLs. Name them meaningfully: "Microsoft Threat Intelligence", "Entra What's New", "M365 Roadmap", "Intune What's New", "Microsoft Security Blog", "Intune What's New", "Purview What's New", etc. Never paste a raw URL as the link text.
- In Risk & Compliance and Planning Horizon, hyperlink each item's bold title directly within its bullet, as shown in the examples above, e.g. **[Storm-2949 breach via stolen identity](url)** — never as a separate raw URL.
- Do NOT omit the Sources line from any section — if no URL is available for a section, link to the most relevant Microsoft documentation page for that topic.

Tone: trusted advisor, calm, factual, direct. Not alarmist. Not dismissive. Like a Friday briefing from your CISO to the board.

Style: Never use em dashes. Use a comma, a colon, a semicolon, or split into two separate sentences instead. Also avoid the contrastive construction "X isn't Y, it's Z" and its variants ("This isn't..., it's...", "That isn't..., it's..."); state the point directly instead of setting up a false contrast first.

Language: American English throughout. Use American spellings — "organization" not "organisation", "behavior" not "behaviour", "license" not "licence", "customize" not "customise", etc."""

LINKEDIN_SYSTEM_PROMPT = """You write the weekly LinkedIn newsletter edition of Modern Work Weekly — a digest for Microsoft 365 engineers, architects, and admins.

Voice: peer-professional, direct, occasionally dry. No first-person "I". Speak to the reader's role — "Intune admins will want to flag this", "Security teams should note", "If your org runs hybrid identity...", "If your C-level asks about AI governance this week, here's the answer." Confident, not hype-y.

Format — optimised for pasting into LinkedIn's newsletter article editor. Use these conventions:
- Section headers in ALL CAPS and bold (wrap in double asterisks: **HEADER**), each prefixed with its fixed emoji anchor (see structure below). These three emoji are the ONLY emoji allowed anywhere in the output — never use emoji in the hook line, body text, bullets, or closing line.
- Top 5 items numbered (1. 2. 3. etc.). Each numbered item is followed by a blank line before the next one starts — never run two numbered items together with no break.
- Secondary bullet points with a dash and space: "- item"
- Blank line between every item and section
- Place a standalone divider line — "⸻" on its own line — between major sections: after the hook line, and between each of TOP 5 / WORTH YOUR ATTENTION / HELP DESK / closing line
- No asterisk dividers, no markdown horizontal rules (---), no backtick code blocks
- Keep total length 400–600 words

Structure (in order):
1. Title — format exactly as: "Modern Work Weekly - Week of YYYY-MM-DD" (plain hyphen, not an em dash; this goes in the LinkedIn article title field, output it on its own line prefixed with "TITLE: ")
2. Hook line — one punchy sentence that names the biggest story this week. No greeting, no "this week in M365". Just the hook.
3. **⚡ TOP 5 THIS WEEK** — the digest content below provides a "CONFIRMED TOP 5" list when available; use exactly those 5 items, in that order, reworded for LinkedIn voice and length, never substituted or reordered. If no confirmed list is provided, select the 5 most important changes yourself. Numbered, one line each, blank line after each. Bold the item title, then a colon, then the explanation. This is the Newsletter edition, read natively inside LinkedIn by subscribers who want the whole thing without leaving the app — give each item a real, complete explanation, not a teaser. (The separate short Announcement post is the one whose only job is earning a click to the site; don't duplicate that job here.) If a source has a real full author name available (not a bare username), it's fine to credit them by name (e.g. "..., per [Name]'s writeup"), but never invent or guess a name that wasn't provided. Format: "1. **Item title:** explanation."
4. **👀 WORTH YOUR ATTENTION** — 2–3 items that aren't urgent but signal where things are heading. One sentence each, dash-prefixed.
5. **🛠️ ONE FOR THE HELP DESK** (optional) — a single change that's going to generate tickets or questions. Skip if nothing fits.
6. Closing line — one short sentence pointing to this week's guides. Format: "This week's guides in the comments!" Do not include a URL in this line - the Technical Digest URL gets posted as the first comment and the Executive's Guide URL as the second comment after publishing, to avoid LinkedIn's reach penalty on posts with outbound links in the body.

Do not include any hashtags in your output — hashtags aren't functional inside LinkedIn's Newsletter article editor, so they're never added to this draft. Do not add a sign-off. Do not wrap output in code fences.

Do not include hyperlinks or Markdown link syntax (no `[text](url)`) anywhere in the output — write plain bolded headline text only, e.g. "**Item title:**". Source links for each item are added automatically after generation by matching your headlines against the links already present in this week's technical post — inventing your own URL here would risk linking to the wrong (or a nonexistent) page.

Style: Never use em dashes. Use a comma, a colon, a semicolon, or split into two separate sentences instead. Also avoid the contrastive construction "X isn't Y, it's Z" and its variants ("This isn't..., it's...", "That isn't..., it's..."); state the point directly instead of setting up a false contrast first.

Language: American English throughout. Use American spellings — "organization" not "organisation", "behavior" not "behaviour", "license" not "licence", "customize" not "customise", etc."""

LINKEDIN_PROMPT_TEMPLATE = """Here is the week's digest content. Produce the LinkedIn newsletter edition.

Week of: {week_of}
Digest URL: https://modernworkweekly.com/posts/{week_of}/

DIGEST CONTENT (Top 5 and category items):
{digest_content}

Output plain text only. No markdown syntax. No preamble."""

# ── LinkedIn announcement/teaser post ────────────────────────────────────────
# The regular native LinkedIn post that accompanies each week's Newsletter
# edition. Previously drafted ad hoc by hand — see feedback_linkedin_hashtags
# memory. Automated because the hand-drafted version kept reproducing the
# newsletter's own content (killing any reason to click through) and burying
# the site link two self-comments deep. This prompt is deliberately the
# opposite of LINKEDIN_SYSTEM_PROMPT: short, teases without explaining, and
# drives to modernworkweekly.com instead of to the Newsletter article.
ANNOUNCEMENT_SYSTEM_PROMPT = """You write the short LinkedIn announcement post that accompanies each week's Modern Work Weekly newsletter — a digest for Microsoft 365 engineers, architects, and admins.

This is a native LinkedIn post, NOT the newsletter itself and not a summary of it. Its only job is to earn a click through to modernworkweekly.com. Never reproduce the newsletter's analysis or "why it matters" explanations here — those live on the site. This post only hints at what's inside.

Voice: peer-professional, direct, occasionally dry, punchier and more informal than the newsletter edition. Confident, not hype-y. First-person is fine here.

Lens of the week: not everyone reading cares about the same thing — a security engineer, a licensing/procurement person, and a helpdesk lead each want a different item leading the post. Before writing, pick exactly ONE governing angle from this list, whichever the week's Top 5 most strongly supports, and frame the whole post (hook and closing question, not necessarily the other fragments) consistently through it. Do not default to "biggest story" or blend two lenses.
- Security/Risk — an active threat, vulnerability, or exposure that demands attention
- Licensing/Cost — a capability that's now included, bundled, or newly billed differently
- End-User Impact — a change end users will notice or generate helpdesk tickets over
- Action Required/Deadline — something with a concrete date or required admin step
- Architecture/Strategic — a structural or governance shift worth planning around
State which lens you picked on its own line first, prefixed "LENS: " (e.g. "LENS: Licensing/Cost"), before the post body. This line is for editorial review only — it gets stripped before posting, never leave it in what actually goes on LinkedIn.

Format:
- Plain text only. No markdown, no bold, no headers, no numbered lists, no emoji section anchors.
- 80-120 words total.
- Opening hook: 1-2 sentences leading with the item that best fits the chosen lens, with one real, specific, credible detail (a product name, a number) but withholding the "so what."
- Then reference 2-3 more items as short headline fragments only, in a sentence or two of prose, not a list. No colon-explanation, no "why it matters" sentence for any of them. Just enough to create curiosity. These don't need to fit the lens, only the hook and closing question do.
- Closing line: an open question inviting a comment, tied to the same lens as the hook (a Licensing lens closes on a licensing question, not a security one). Never a generic "thoughts?"
- Do not include a URL anywhere in the body. The link is posted separately as the first comment immediately after publishing, to avoid LinkedIn's reach penalty on posts with outbound links in the body.
- Do not write "link in comments," "full digest below," or any variant as a separate closing line — the question is the close.
- Never estimate or promise a reading time ("five minute read," "quick read," etc.) — the digest's actual length varies week to week, and a wrong promise breaks trust before the reader even clicks. If you want urgency, tie it to relevance instead ("before your next license renewal conversation," "before Friday," "before your next travel booking"), never a time commitment.

Do not use em dashes. Do not use the contrastive "X isn't Y, it's Z" construction. American English spellings throughout ("organization," "behavior," "license," "customize")."""

ANNOUNCEMENT_PROMPT_TEMPLATE = """Here is this week's confirmed Top 5 (already reviewed and published in the technical post). Produce the short LinkedIn announcement post that teases this content without explaining it.

Week of: {week_of}

CONFIRMED TOP 5 (choose the single strongest lead story for the hook; name 2-3 more only as headline fragments; do not use all 5, do not explain any of them, do not invent items not listed here):
{top5_lines}

Output plain text only. No markdown. No preamble."""

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

RAW GITHUB DOC COMMIT DATA (for the optional Documentation Updates section — most of these are noise, see the system prompt's selection criteria for which ones actually qualify):
{doc_updates}

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


# pending_draft.json accumulates across however many scraper runs happen
# before the next digest publishes, and scraper.py's own backstop is
# deliberately loose (21 days, see MAX_PENDING_AGE_DAYS in scraper.py) to
# tolerate irregular cron cadence. This is the tighter gate that actually
# decides what's allowed into a published digest, exec briefing, or LinkedIn
# draft: confirmed real examples (Oct 2025, Nov 2025, Mar 2026 posts) were
# sitting in this same accumulated data with zero filtering at prompt-build
# time before this existed.
MAX_AGE_DAYS = 7


DEADLINE_CANDIDATES_FILE = STATE_DIR / "deadline_candidates.json"

# site/data/deadlines.json only ever loses entries automatically — the 8-hour
# purge in scraper.py drops anything past its date. Nothing adds to it
# automatically, which is how it quietly shrank to a single entry after
# three weeks of digests (06-30, 07-07, 07-14) had real dated items — an EWS
# disablement deadline, two Teams Rooms GA targets, a Copilot GCC GA target —
# that never got manually added. This is a lightweight, human-in-the-loop
# net: it flags items that *sound* dated so they get a look during the
# Step 2 weekly review (see docs/WEEKLY_WORKFLOW.md), it does not write to
# deadlines.json itself, since "target availability August 2026" needs a
# human to pick a real date, and some items ("a future update", no date
# given) can't be dated at all yet.
# Retirement/deprecation language is inherently forward-looking even before
# Microsoft names an exact date (see OWA Light: "will retire... no specific
# date is given yet") — always worth a look.
DEADLINE_KEYWORDS_ALWAYS = [
    "retire", "retirement", "retiring", "deprecat", "end of support",
    "end of life", "eos", "eol", "disablement", "disabl", "sunset",
    "discontinue",
]

# Rollout/availability language is only a "key date" if a date was actually
# found nearby — "Sales Agent is now generally available" with no date is a
# normal GA announcement (already happened, nothing to calendar), not a
# future deadline. Requiring a date here is what keeps this list from
# flooding with every routine GA item each week.
DEADLINE_KEYWORDS_NEEDS_DATE = [
    "generally available", "general availability", "target availability",
    "target ga", "ga target", "targeted for", "rolling out", "coming to",
    "will be available", "available starting", "begins rolling out",
    "starts rolling out",
]

_MONTH_YEAR_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September"
    r"|October|November|December)\s+(\d{1,2},?\s+)?(20\d{2})\b",
    re.IGNORECASE,
)
_QUARTER_YEAR_RE = re.compile(r"\bQ([1-4])\s+(20\d{2})\b", re.IGNORECASE)

# Microsoft 365 Roadmap descriptions embed the actual target date as
# structured text — e.g. "...GA date: September CY2026" or "...Preview
# date: August CY2026" — a real, Microsoft-confirmed target, not vague
# prose. _MONTH_YEAR_RE doesn't catch it: Roadmap's "CY" year prefix
# ("CY2026") isn't a bare "2026" immediately after the month, so the two
# patterns never overlap. This is checked as its own signal, independent of
# DEADLINE_KEYWORDS_NEEDS_DATE, because "GA date:" / "Preview date:" IS the
# target-date announcement — no separate keyword needed to justify flagging
# it. Confirmed live against the 2026-08-16 Roadmap feed: none of these
# items were being caught by the generic patterns above, so Roadmap GA/
# Preview targets were relying entirely on manual spotting during weekly
# review instead of showing up in deadline_candidates.json.
_ROADMAP_DATE_RE = re.compile(
    r"\b(GA date|Preview date):\s*"
    r"(January|February|March|April|May|June|July|August|September"
    r"|October|November|December)\s+CY(20\d{2})",
    re.IGNORECASE,
)


def _extract_roadmap_date(text: str) -> tuple[str | None, str | None]:
    """Pull a Roadmap-style 'GA date: <Month> CY<yyyy>' / 'Preview date:
    <Month> CY<yyyy>' out of item text. Prefers GA over Preview when both
    are present (GA is the harder commitment, more worth calendaring).
    Returns (label, "Month YYYY") or (None, None) if neither is found.
    """
    matches = {m.group(1).lower(): m for m in _ROADMAP_DATE_RE.finditer(text)}
    for label in ("ga date", "preview date"):
        m = matches.get(label)
        if m:
            return m.group(1), f"{m.group(2)} {m.group(3)}"
    return None, None


def _guess_deadline_type(matched_kw: str, text_lower: str) -> str:
    """Best-effort guess at the Key Dates entry type, so a future weekly
    review starts from a suggestion instead of hand-classifying every
    candidate from scratch. Matches the "deadline"/"feature"/"report" types
    in site/data/deadlines.json and $typeLabels in deadlines.html — always
    reviewed by a human before it's actually added there, same as the date
    and pillar already are (see write_deadline_candidates()/WEEKLY_WORKFLOW.md).

    "deadline" = a real forced-action cutoff (retirement, disablement, EOS,
    compliance deadline) — matches DEADLINE_KEYWORDS_ALWAYS or the signal
    text itself.
    "report" = a new reporting/visibility capability, not a rollout with
    cutoff pressure — a loose keyword check, deliberately narrow so it
    only fires on real report-shaped language rather than every mention of
    the word "report" in body text.
    "feature" = everything else (the common case: a GA/rollout item worth
    knowing about, no cutoff to prep for).
    """
    if matched_kw.lower() in [kw.lower() for kw in DEADLINE_KEYWORDS_ALWAYS]:
        return "deadline"
    if re.search(r"\breport(s|ing)?\b", text_lower):
        return "report"
    return "feature"


def detect_deadline_candidates(draft: dict) -> list[dict]:
    """Scan this week's accumulated items for retirement/deprecation/GA-date
    language so nothing dated silently misses site/data/deadlines.json.

    Returns a list of {title, url, source, pillar, signal, extracted_date,
    structured}. extracted_date is the raw matched text (e.g. "August 2026")
    or None if a retirement/deprecation signal hit but no date-like text was
    found nearby — those still get surfaced as a "watch for a date" item
    rather than dropped, since Microsoft often confirms the direction before
    the date. structured=True marks candidates pulled from Roadmap's own
    "GA date:"/"Preview date:" line rather than regex-matched prose — those
    are Microsoft-confirmed targets, not an inference, so they're safe to
    approve faster during weekly review.
    """
    candidates = []
    for cat, items in draft.get("grouped_items", {}).items():
        for item in items:
            text = f"{item.get('title', '')} {item.get('body', '')}"
            text_lower = text.lower()

            roadmap_label, roadmap_date = _extract_roadmap_date(text)
            structured = roadmap_date is not None
            if structured:
                extracted_date = roadmap_date
                matched_kw = roadmap_label
            else:
                date_match = _MONTH_YEAR_RE.search(text) or _QUARTER_YEAR_RE.search(text)
                extracted_date = date_match.group(0) if date_match else None

                matched_kw = next(
                    (kw for kw in DEADLINE_KEYWORDS_ALWAYS if kw in text_lower), None
                )
                if not matched_kw and extracted_date:
                    matched_kw = next(
                        (kw for kw in DEADLINE_KEYWORDS_NEEDS_DATE if kw in text_lower), None
                    )
                if not matched_kw:
                    continue

            candidates.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "pillar": cat,
                "signal": matched_kw.strip(),
                "extracted_date": extracted_date,
                "structured": structured,
                "suggested_type": _guess_deadline_type(matched_kw, text_lower),
            })
    return candidates


def clean_dashes(text: str) -> str:
    """Deterministic backstop for the "never use em dashes" style rule.

    Every SYSTEM_PROMPT in this file has told Claude not to use em dashes
    since this rule was first added, but the live 2026-07-21 post proved
    the model doesn't reliably follow it (em dashes throughout). Rather
    than trust a prompt instruction a second time, strip them here so
    compliance doesn't depend on the model's mood. Covers em dash (—,
    U+2014) and en dash (–, U+2013); both are typically already surrounded
    by spaces in Claude's output, so a straight character swap is enough.
    Deliberately does NOT touch the three-em dash (⸻, U+2E3B) — that's the
    intentional LinkedIn section divider character, a different glyph.
    """
    return text.replace("—", "-").replace("–", "-")


def write_deadline_candidates(candidates: list[dict]) -> Path:
    STATE_DIR.mkdir(exist_ok=True)
    with open(DEADLINE_CANDIDATES_FILE, "w") as f:
        json.dump(
            {
                "generated": datetime.now(timezone.utc).date().isoformat(),
                "candidates": candidates,
            },
            f,
            indent=2,
        )
    return DEADLINE_CANDIDATES_FILE


def filter_recent(items: list, max_age_days: int = MAX_AGE_DAYS) -> list:
    """Drop items older than max_age_days based on a parsed publish date.

    Items with an unparseable date are kept (and logged) rather than
    silently dropped — an item we can't date is not evidence it's stale.
    """
    fresh = []
    for item in items:
        age = item_age_days(item.get("date"))
        if age is None:
            log.warning(
                f"Could not parse date for '{item.get('title', '?')[:60]}' "
                f"(source={item.get('source')}, raw date={item.get('date')!r}) — "
                f"keeping it rather than risk dropping real content."
            )
            fresh.append(item)
            continue
        if age <= max_age_days:
            fresh.append(item)
        else:
            log.info(
                f"Freshness filter: excluding '{item.get('title', '?')[:60]}' "
                f"from {item.get('source')} — {age:.0f} days old."
            )
    return fresh


def build_prompt(draft: dict, max_age_days: int = MAX_AGE_DAYS) -> str:
    # Compact the grouped items to save tokens — keep title, body, phase, admin_action.
    # Filter to the last max_age_days days first (parsed dates, not raw string
    # comparison — see dateutils.py), then cap at MAX_PER_CAT items per
    # category, most recent first. This was 8 until 2026-07-21, when a
    # backlog-recovery week showed Claude producing only 5 of 7 available
    # Identity & Access items — well under even the old cap — revealing the
    # real ceiling was Claude's own selectivity, not this number. Raised to
    # 20 as a generous token-budget safety valve (Sonnet's context window
    # makes the old "keep prompt under 8k tokens" rationale obsolete) rather
    # than removed outright, so a truly pathological accumulation still has
    # *some* backstop. The SYSTEM_PROMPT now also explicitly instructs
    # Claude to include every item provided, not a self-selected subset.
    #
    # max_age_days defaults to the standard 7-day window but can be widened
    # via --max-age-days for a one-off regeneration when a real backlog has
    # built up (e.g. 2026-07-21: production drift meant several genuinely
    # new items from 07-08 through 07-13 never got consumed by the 07-14
    # run, and by the time 07-21 ran they'd aged past 7 days). Don't lower
    # the module-level MAX_AGE_DAYS default to "fix" a one-time backlog —
    # that filter is what stops stale multi-week content from flooding a
    # normal week.
    MAX_PER_CAT = 20
    compact = {}
    for cat, items in draft.get("grouped_items", {}).items():
        # "Research & Trends" (Viva WorkLab research essays) is exec-only
        # content — the technical digest's six pillar sections and its
        # prompt format have no place for it, so it's excluded here rather
        # than forced into a mismatched category.
        if cat == "Research & Trends":
            continue
        fresh_items = filter_recent(items, max_age_days=max_age_days)
        # Sort by parsed date descending so the cap keeps the genuinely most
        # recent items — the old raw-string sort didn't sort correctly across
        # ISO 8601 vs RFC 822 vs RFC-822-with-" Z" date formats.
        sorted_items = sorted(
            fresh_items,
            key=lambda x: parse_item_date(x.get("date")) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        compact[cat] = [
            {
                "title": item["title"],
                "body": item["body"],
                "source": item["source"],
                "phase": item.get("phase", "GA"),
                "admin_action": item.get("admin_action"),
                "url": item.get("url", ""),
                # Real MSRC severity data (scraper.py's fetch_cve_severity),
                # only ever populated on actual CVE items from the MSRC
                # source. Passed through so Claude relays real Microsoft
                # data in Action Required instead of guessing severity from
                # the write-up.
                "cve_severity": item.get("cve_severity"),
                "cve_base_score": item.get("cve_base_score"),
                "cve_exploited": item.get("cve_exploited"),
            }
            for item in sorted_items[:MAX_PER_CAT]
        ]

    # Documentation Updates: same freshness filter and recency sort as
    # category items above, capped per pillar (these lists are almost always
    # much shorter than a category's item count, so a lower cap is enough
    # of a token-budget safety valve without ever realistically being hit).
    MAX_PER_PILLAR_DOCS = 15
    doc_compact = {}
    for pillar, items in draft.get("doc_updates", {}).items():
        fresh_items = filter_recent(items, max_age_days=max_age_days)
        sorted_items = sorted(
            fresh_items,
            key=lambda x: parse_item_date(x.get("date")) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        if sorted_items:
            doc_compact[pillar] = [
                {
                    "title": item["title"],
                    "url": item.get("url", ""),
                    "repo": item.get("repo", ""),
                }
                for item in sorted_items[:MAX_PER_PILLAR_DOCS]
            ]

    return DIGEST_PROMPT_TEMPLATE.format(
        week_of=draft.get("week_of", datetime.now(timezone.utc).date().isoformat()),
        total_new_items=draft.get("total_new_items", 0),
        sources=", ".join(draft.get("sources_checked", [])),
        grouped_items=json.dumps(compact, indent=2),
        doc_updates=json.dumps(doc_compact, indent=2) if doc_compact else "(none this week)",
    )


def call_claude(prompt: str) -> str:
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment
    log.info("Calling Claude API (claude-sonnet-4-6)...")
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def build_exec_prompt(draft: dict, max_age_days: int = MAX_AGE_DAYS) -> str:
    # Unlike build_prompt(), this previously had no recency filter or cap at
    # all — every accumulated item, however old, was handed straight to
    # Claude. Apply the same freshness gate so the Executive's Guide can't
    # drift stale independently of the technical post. max_age_days follows
    # the same --max-age-days override as build_prompt() (see its comment).
    compact = {}
    # Viva "Research Drop" essays publish roughly monthly, so the standard
    # 7-day window almost always misses them between one weekly digest run
    # and the next. Give this bucket alone a 30-day window so it actually
    # gets a fair chance to reach the Executive's Guide, regardless of
    # whatever max_age_days is in effect for everything else.
    RESEARCH_MAX_AGE_DAYS = 30
    for cat, items in draft.get("grouped_items", {}).items():
        max_age = RESEARCH_MAX_AGE_DAYS if cat == "Research & Trends" else max_age_days
        fresh_items = filter_recent(items, max_age_days=max_age)
        compact[cat] = [
            {
                "title": item["title"],
                "body": item["body"],
                "source": item["source"],
                "phase": item.get("phase", "GA"),
                "admin_action": item.get("admin_action"),
                "url": item.get("url", ""),
            }
            for item in fresh_items
        ]
    return EXEC_DIGEST_PROMPT_TEMPLATE.format(
        week_of=draft.get("week_of", datetime.now(timezone.utc).date().isoformat()),
        total_new_items=draft.get("total_new_items", 0),
        grouped_items=json.dumps(compact, indent=2),
    )


# ── LinkedIn hashtags ────────────────────────────────────────────────────────
# Maps the standard tag taxonomy (the same one used in the technical post's
# front matter — see SYSTEM_PROMPT above) to clean, readable hashtags. Keeps
# hashtag selection deterministic: derived from the tags Claude actually
# assigned to this week's post, not a separate free-form guess by the
# LinkedIn-drafting call.
TAG_HASHTAGS = {
    "intune": "#Intune",
    "entra-id": "#EntraID",
    "defender-xdr": "#DefenderXDR",
    "defender-for-endpoint": "#DefenderForEndpoint",
    "defender-for-office-365": "#DefenderForOffice365",
    "windows-autopatch": "#WindowsAutopatch",
    "autopilot": "#Autopilot",
    "windows-365": "#Windows365",
    "purview": "#Purview",
    "teams": "#MicrosoftTeams",
    "sharepoint": "#SharePoint",
    "onedrive": "#OneDrive",
    "exchange": "#Exchange",
    "copilot": "#Copilot",
    "copilot-studio": "#CopilotStudio",
    "zero-trust": "#ZeroTrust",
    "modern-work": "#ModernWork",
    "identity": "#Identity",
    "endpoint-management": "#EndpointManagement",
    "conditional-access": "#ConditionalAccess",
    "global-secure-access": "#GlobalSecureAccess",
    "viva": "#Viva",
    "windows": "#Windows",
    "teams-rooms": "#TeamsRooms",
    "data-lifecycle": "#DataLifecycle",
    "shadow-ai": "#ShadowAI",
    "dspm": "#DSPM",
    "hotpatch": "#Hotpatch",
    "power-platform": "#PowerPlatform",
}


def extract_post_tags(content: str) -> list:
    """Pull the `tags:` list out of a generated post's YAML front matter.

    Expects the block form Claude actually produces:
        tags:
          - intune
          - copilot
    Falls back to inline list form `tags: [intune, copilot]` if present.
    Returns tag slugs in the order they appear (front matter tags are
    typically already ordered by relevance).
    """
    front_matter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not front_matter_match:
        return []
    front_matter = front_matter_match.group(1)

    block_match = re.search(r"^tags:\s*\n((?:[ \t]*-[ \t]*.+\n?)+)", front_matter, re.MULTILINE)
    if block_match:
        return [
            line.strip().lstrip("-").strip().strip('"\'')
            for line in block_match.group(1).splitlines()
            if line.strip()
        ]

    inline_match = re.search(r"^tags:\s*\[(.*?)\]", front_matter, re.MULTILINE)
    if inline_match:
        return [t.strip().strip('"\'') for t in inline_match.group(1).split(",") if t.strip()]

    return []


# Always included first, on every post, regardless of that week's tags --
# the site's own brand hashtag.
BRAND_HASHTAG = "#ModernWork"

# Both the automated announcement-post comment URL below, and the
# Executive's Guide URL Ryan adds by hand as the Newsletter's second
# comment, are plain links with no query string — see
# feedback_linkedin_hashtags memory for why both links only ever appear
# in comments, never in a post body. UTM tracking params were dropped
# 2026-08-25: the long query string made the link look cluttered/spammy
# on LinkedIn and risked deterring clicks, which mattered more than the
# attribution data.


def modernworkweekly_url(path: str) -> str:
    """Build a plain modernworkweekly.com URL, no query string.

    path: e.g. "posts/2026-08-11" or "exec/2026-08-11" (no leading/trailing slash needed)
    """
    path = path.strip("/")
    return f"https://modernworkweekly.com/{path}/"


def build_hashtags(tags: list, max_tags: int = 3) -> list:
    """Convert post tags into hashtags via the compiled TAG_HASHTAGS map.

    Always leads with BRAND_HASHTAG, then up to max_tags content-derived
    hashtags. Preserves order, dedupes, skips anything not in the map.
    """
    hashtags = [BRAND_HASHTAG]
    for tag in tags:
        hashtag = TAG_HASHTAGS.get(tag)
        if hashtag and hashtag not in hashtags:
            hashtags.append(hashtag)
        if len(hashtags) >= max_tags + 1:
            break
    return hashtags


# ── LinkedIn source links ────────────────────────────────────────────────────
# The technical post already cites a real source URL for every item, in the
# form **[Title](url)**. Rather than letting the LinkedIn-drafting call invent
# its own links (risking a hallucinated or mismatched URL), we extract every
# (title, url) pair already present in the published post and match the
# LinkedIn draft's headlines against them by word overlap. A headline only
# gets linked if a confident match is found — otherwise it stays plain bold.
_LINK_STOPWORDS = {
    "ga", "preview", "now", "microsoft", "new", "for", "in", "the", "and",
    "of", "with", "is", "to", "a", "on", "public", "general", "availability",
    "announced", "announces", "update", "updates", "released", "this",
    "your", "are", "an", "at", "from", "via",
}


def _title_words(title: str) -> set:
    """Normalize a headline into a set of significant (stopword-free) words."""
    cleaned = re.sub(r"[^\w\s]", " ", title.lower())
    return {w for w in cleaned.split() if w and w not in _LINK_STOPWORDS}


def extract_post_links(content: str) -> list:
    """Pull every **[Title](url)** markdown link out of the technical post body.

    Returns a list of (title, url, wordset) tuples covering every item in
    every section — Top 5 and category sections alike — since the LinkedIn
    draft's "Worth Your Attention" and "Help Desk" items are pulled from
    anywhere in the digest, not just Top 5.
    """
    links = []
    for title, url in re.findall(r"\*\*\[([^\]]+)\]\(([^)]+)\)\*\*", content):
        links.append((title, url, _title_words(title)))
    return links


def _best_link_match(headline: str, links: list, min_overlap: float = 0.6):
    """Find the source URL whose title best overlaps with a LinkedIn headline.

    Uses an overlap coefficient (shared words / smaller word-set size) over
    stopword-filtered word sets, rather than Jaccard. Jaccard divides by the
    union of both sets, which punishes a short, punchy LinkedIn headline
    against a long, specific post title even when every word in the short
    one appears in the long one. The overlap coefficient only cares whether
    the smaller set is mostly contained in the larger one, which is what
    "same story, reworded" actually looks like.

    Requires both word sets to have at least 2 significant words unless they
    match exactly — guards against one-word coincidental overlap inflating
    the score on very short headlines.

    Returns None (never a guess) if nothing clears the overlap threshold.
    """
    headline_words = _title_words(headline)
    if not headline_words:
        return None
    best_url, best_score = None, 0.0
    for _title, url, title_words in links:
        if not title_words:
            continue
        shared = headline_words & title_words
        smaller = min(len(headline_words), len(title_words))
        if smaller < 2 and headline_words != title_words:
            continue
        score = len(shared) / smaller
        if score > best_score:
            best_score, best_url = score, url
    return best_url if best_score >= min_overlap else None


# ── Top 5 category tagging ───────────────────────────────────────────────────
# collapsible.js colors each Top 5 badge and each category section
# independently: section headers get their color from their own literal H2
# text, but Top 5 badges are colored by detectPillar(), a client-side regex
# guess that has no visibility into which section the item actually landed
# in. Most weeks this goes unnoticed because the guessed category usually
# matches *some* real section on the page; a week that collapses to one
# category (e.g. 2026-07-28) exposes the mismatch directly, since the guess
# can land on a category that has no section on the page at all.
#
# Fix is deterministic post-processing here, not a stronger prompt
# instruction: prompt-only formatting rules aren't reliable enough for hard
# requirements even when explicit (see clean_dashes()/MAX_PER_CAT
# precedent). This tags each Top 5 item with the real category section its
# title best matches, using the same overlap-matching already proven for
# LinkedIn headline linking (_best_link_match). collapsible.js reads the tag
# when present and only falls back to detectPillar() for older posts
# published before this existed.
CATEGORY_NAMES = [
    "Identity & Access",
    "Endpoint & Device Management",
    "Collaboration & Productivity",
    "AI & Copilot",
    "Employee Experience",
    "Security & Compliance",
]
_CATEGORY_NAME_SET = {name.lower() for name in CATEGORY_NAMES}

_CATEGORY_SECTION_RE = re.compile(r"^## (?P<heading>.+?)\s*\n(?P<body>.*?)(?=\n## |\Z)", re.MULTILINE | re.DOTALL)
_CATEGORY_ITEM_RE = re.compile(r"^-\s+\*\*(?:\[(?P<linked>[^\]]+)\]\([^)]+\)|(?P<plain>[^*]+))\*\*", re.MULTILINE)


def extract_category_sections(content: str) -> dict[str, list[str]]:
    """Map each real category section heading in a generated post to the
    titles of the items actually placed under it.

    This is the ground truth for tag_top5_categories() below: rather than
    trusting Claude to self-report a Top 5 item's category, or re-guessing
    it client-side from keywords, we read it straight from the section
    Claude actually filed the item under in this same post.
    """
    sections: dict[str, list[str]] = {}
    for m in _CATEGORY_SECTION_RE.finditer(content):
        heading = m.group("heading").strip()
        if heading.lower() not in _CATEGORY_NAME_SET:
            continue
        titles = [
            (item.group("linked") or item.group("plain") or "").strip()
            for item in _CATEGORY_ITEM_RE.finditer(m.group("body"))
        ]
        titles = [t for t in titles if t]
        if titles:
            sections[heading] = titles
    return sections


def _stem_words(words: set) -> set:
    """Very light plural normalization (strip a trailing 's' on words longer
    than 3 chars) so e.g. 'label' vs 'labels' don't cost overlap score.
    Deliberately naive — good enough for matching a Top 5 headline against
    the same story's own category-section title (same underlying item,
    independently reworded by Claude), not general-purpose stemming.
    """
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words}


def _best_category_match(headline: str, catalog: list, min_overlap: float = 0.5):
    """Like _best_link_match, but with light plural normalization and a
    lower confidence bar (0.5 vs 0.6). A lower bar is appropriate here
    because a miss just falls back to the pre-existing client-side color
    guess (cosmetic), not a wrong hyperlink like _best_link_match guards
    against — so the cost of a false negative is higher than the cost of
    a marginal false positive, the opposite trade-off from link matching.
    """
    headline_words = _stem_words(_title_words(headline))
    if not headline_words:
        return None
    best_category, best_score = None, 0.0
    for _title, category, title_words in catalog:
        title_words = _stem_words(title_words)
        if not title_words:
            continue
        shared = headline_words & title_words
        smaller = min(len(headline_words), len(title_words))
        if smaller < 2 and headline_words != title_words:
            continue
        score = len(shared) / smaller
        if score > best_score:
            best_score, best_category = score, category
    return best_category if best_score >= min_overlap else None


def tag_top5_categories(content: str) -> str:
    """Tag each Top 5 item with the real category section it best matches,
    via an inline {{< cat "..." >}} shortcode right after the bold title.

    An item with no confident match is left untagged; collapsible.js falls
    back to its own keyword guess for that one item, same as it already
    does for every pre-existing post.
    """
    sections = extract_category_sections(content)
    if not sections:
        return content

    catalog = [
        (title, category, _title_words(title))
        for category, titles in sections.items()
        for title in titles
    ]

    top5_match = _TOP5_SECTION_RE.search(content)
    if not top5_match:
        return content

    def tag_item(m):
        title = m.group("title").strip()
        category = _best_category_match(title, catalog)
        if category:
            # A space is required before the shortcode call -- without it,
            # Goldmark fails to close the ** emphasis run (placeholder sits
            # directly against the delimiter) and the title renders as
            # literal asterisks instead of <strong>. That silently breaks
            # collapsible.js: makeTop5Collapsible() requires a <strong> in
            # each Top 5 <li> to build the item. Confirmed live on the
            # 2026-08-11 post, the first week this tagging shipped -- all 5
            # Top 5 items vanished from the page.
            return f"**{title}** {{{{< cat \"{category}\" >}}}}"
        return m.group(0)

    tagged_block = re.sub(r"\*\*(?P<title>[^*]+)\*\*(?=\s*-\s)", tag_item, top5_match.group(1))
    return content[: top5_match.start(1)] + tagged_block + content[top5_match.end(1) :]


_EMPHASIS_SHORTCODE_RE = re.compile(r'\{\{<\s*emphasis\s+"([^"]*)"\s*>\}\}')
# A bullet/numbered-item start: "- **" or "1. **" at the start of a line.
# Used to find the boundaries of the item the shortcode sits inside, since
# the shortcode appears early in the bullet (right after the phase tag,
# BEFORE the actual descriptive sentence) — scoring only the text *before*
# the shortcode would mostly capture the title/link and miss the
# keyword-bearing prose entirely.
_ITEM_BOUNDARY_RE = re.compile(r'^\s*(?:[-*]|\d+\.)\s+\*\*', re.MULTILINE)


def check_emphasis_tags(content: str, week_of: str) -> None:
    """Lightweight keyword sanity check on Claude-assigned emphasis tags.

    Added 2026-08-29 alongside the emphasis-tag feature itself (see
    SYSTEM_PROMPT/EXEC_SYSTEM_PROMPT). This does NOT decide or correct
    emphasis tags — Claude's judgment is the actual classification, since
    keyword matching can't reliably catch a case like "DLP for Copilot is
    really a Data story" (see the 2026-08-29 Intune classification audit
    for why keyword-only classification has real blind spots). This
    function only flags disagreement for human review: an item Claude
    tagged with zero supporting keyword signal, or an item with a strong
    keyword signal for a tag Claude didn't use. Purely observational,
    mirrors write_classification_stats() in scraper.py — never blocks
    publishing, never rewrites content.
    """
    boundaries = [b.start() for b in _ITEM_BOUNDARY_RE.finditer(content)]

    findings = []
    for m in _EMPHASIS_SHORTCODE_RE.finditer(content):
        raw_tags = [t.strip() for t in m.group(1).split(",") if t.strip()]
        unknown = [t for t in raw_tags if t not in EMPHASIS_TAGS]

        # Find the enclosing item's full span: the last bullet-start at or
        # before the shortcode, through the next bullet-start after it (or
        # end of content). This captures the whole bullet — title, phase
        # tag, and the descriptive sentence(s) that follow the shortcode —
        # not just whatever happens to precede the shortcode itself.
        item_start = max((b for b in boundaries if b <= m.start()), default=max(0, m.start() - 200))
        item_end = min((b for b in boundaries if b > m.start()), default=len(content))
        window = content[item_start:item_end].lower()

        keyword_hits = {
            tag: [kw for kw in kws if kw in window]
            for tag, kws in EMPHASIS_KEYWORDS.items()
        }
        supported = {t for t in raw_tags if keyword_hits.get(t)}
        unsupported = [t for t in raw_tags if t not in supported and t not in unknown]
        # Tags with a strong keyword signal (2+ hits) that Claude didn't use.
        missed = [
            tag for tag, hits in keyword_hits.items()
            if len(hits) >= 2 and tag not in raw_tags
        ]
        if unknown or unsupported or missed:
            title_match = re.search(r'\*\*([^*]+)\*\*', content[item_start:m.start()])
            findings.append({
                "title": title_match.group(1) if title_match else "(title not found)",
                "assigned": raw_tags,
                "unknown_tags": unknown,
                "unsupported_tags": unsupported,
                "keyword_suggests_instead": missed,
            })

    history = []
    if EMPHASIS_STATS_FILE.exists():
        try:
            with open(EMPHASIS_STATS_FILE) as f:
                history = json.load(f).get("history", [])
        except Exception as e:
            log.warning(f"Could not read {EMPHASIS_STATS_FILE}, starting fresh: {e}")

    total_tagged = len(_EMPHASIS_SHORTCODE_RE.findall(content))
    entry = {
        "week_of": week_of,
        "total_emphasis_tags": total_tagged,
        "flagged_count": len(findings),
        "flagged": findings[:15],
    }
    history.append(entry)
    history = history[-EMPHASIS_STATS_HISTORY_LIMIT:]

    with open(EMPHASIS_STATS_FILE, "w") as f:
        json.dump({"history": history}, f, indent=2)

    if findings:
        log.info(
            f"Emphasis tag check — {total_tagged} tags assigned, "
            f"{len(findings)} flagged for review → {EMPHASIS_STATS_FILE}"
        )
    else:
        log.info(f"Emphasis tag check — {total_tagged} tags assigned, none flagged.")


# ── Homepage card quick signals ─────────────────────────────────────────────
# The homepage card for each week (site/layouts/_default/list.html) shows a
# reader two quick signals before they click through: how many CVEs this
# week touches and how many Action Required items are flagged. Counted here,
# post-generation, from Claude's own output — same reasoning as
# extract_category_sections()/tag_top5_categories() above: a self-reported
# count in the prompt is exactly the kind of soft instruction that drifts,
# deterministic post-processing doesn't (see clean_dashes()/MAX_PER_CAT
# precedent). Added 2026-08-06.
_CVE_RE = re.compile(r"CVE-\d{4,}-\d+", re.IGNORECASE)
_ACTION_REQUIRED_SECTION_RE = re.compile(
    r"^## Action Required\s*\n(?P<body>.*?)(?=\n## |\Z)", re.MULTILINE | re.DOTALL
)


def compute_card_stats(content: str) -> dict:
    """Count CVEs (deduped) and Action Required bullets in a generated post."""
    cve_count = len({m.group(0).upper() for m in _CVE_RE.finditer(content)})
    action_required_count = 0
    ar_match = _ACTION_REQUIRED_SECTION_RE.search(content)
    if ar_match:
        action_required_count = len(list(_CATEGORY_ITEM_RE.finditer(ar_match.group("body"))))
    return {"cve_count": cve_count, "action_required_count": action_required_count}


def validate_all_cves_in_action_required(content: str) -> None:
    """Code-level check for the "every CVE goes in Action Required" rule --
    a prompt instruction is a request, not a guarantee (see the prompt-
    reliability lesson from em-dash/category-truncation drift), so this
    verifies it actually happened rather than trusting Claude followed the
    SYSTEM_PROMPT rule. Logs a warning naming any CVE that appears
    elsewhere in the post but not inside Action Required; does not modify
    the content or block publishing, since a human reviews every post
    before it goes out per the standard weekly workflow."""
    all_cves = {m.group(0).upper() for m in _CVE_RE.finditer(content)}
    ar_match = _ACTION_REQUIRED_SECTION_RE.search(content)
    ar_cves = set()
    if ar_match:
        ar_cves = {m.group(0).upper() for m in _CVE_RE.finditer(ar_match.group("body"))}
    missing = all_cves - ar_cves
    if missing:
        log.warning(
            f"  {len(missing)} CVE(s) present in the post but missing from Action Required: "
            f"{', '.join(sorted(missing))}. Review before publishing per Ryan's CVE policy."
        )

def inject_card_stats(content: str) -> str:
    """Write compute_card_stats() into the post's front matter as
    `cve_count:` / `action_required_count:`, inserted immediately before the
    `sources:` block. If the front matter doesn't have a top-level
    `sources:` line in the expected place, leave content untouched rather
    than guess where to insert — the homepage card simply omits the signal
    chips for that post (list.html guards with `default 0`)."""
    stats = compute_card_stats(content)
    front_matter_match = re.match(r"^(---\s*\n.*?)(^sources:\s*\n)", content, re.DOTALL | re.MULTILINE)
    if not front_matter_match:
        return content
    stats_block = f"cve_count: {stats['cve_count']}\naction_required_count: {stats['action_required_count']}\n"
    return content[: front_matter_match.end(1)] + stats_block + content[front_matter_match.end(1) :]


# ── Executive's Guide card quick signals ────────────────────────────────────
# Same idea as the technical post's cve_count/action_required_count above,
# but exec posts don't have a source list or multi-pillar categories to key
# off of (front matter categories is always the single value "Executive
# Guide" — see the system prompt). What they do have is "The Week at a
# Glance", four bullets each hand-flagged 🔴/🟡/🟢 by risk level — exactly
# the signal an executive scanning the list page wants (is there something
# red this week?), and it already matches the red/orange/green palette the
# single exec page's own risk dashboard uses (exec-stat-card-high/med/low).
# Added 2026-08-06.
_EXEC_FRONT_MATTER_RE = re.compile(r"^(---\s*\n.*?\n)(---\s*\n)", re.DOTALL)
_WEEK_AT_GLANCE_RE = re.compile(
    r"^## The Week at a Glance\s*\n(?P<body>.*?)(?=\n## |\Z)", re.MULTILINE | re.DOTALL
)


def compute_exec_risk_stats(content: str) -> dict:
    """Count 🔴/🟡/🟢-flagged bullets in the exec post's Week at a Glance."""
    match = _WEEK_AT_GLANCE_RE.search(content)
    body = match.group("body") if match else ""
    return {
        "risk_high": len(re.findall(r"^-\s*🔴", body, re.MULTILINE)),
        "risk_med": len(re.findall(r"^-\s*🟡", body, re.MULTILINE)),
        "risk_low": len(re.findall(r"^-\s*🟢", body, re.MULTILINE)),
    }


def inject_exec_risk_stats(content: str) -> str:
    """Write compute_exec_risk_stats() into the exec post's front matter as
    `risk_high:`/`risk_med:`/`risk_low:`, inserted right before the closing
    `---`. Leaves content untouched if front matter can't be found."""
    stats = compute_exec_risk_stats(content)
    m = _EXEC_FRONT_MATTER_RE.match(content)
    if not m:
        return content
    stats_block = (
        f"risk_high: {stats['risk_high']}\n"
        f"risk_med: {stats['risk_med']}\n"
        f"risk_low: {stats['risk_low']}\n"
    )
    return content[: m.end(1)] + stats_block + content[m.end(1) :]


def _draft_links(draft: dict) -> list:
    """Pull (title, url, wordset) triples straight from the raw scraped items
    in this week's draft.

    These titles come straight from the source (Microsoft's changelog/blog),
    before either the technical post or the LinkedIn edition paraphrased
    them. Matching a LinkedIn headline against this title is one paraphrase
    hop; matching it against the post's already-Claude-rewritten title is
    two independent paraphrase hops of the same original story, which is
    why topically-identical headlines can share almost no literal words.
    """
    links = []
    for items in draft.get("grouped_items", {}).values():
        for item in items:
            title, url = item.get("title"), item.get("url")
            if title and url:
                links.append((title, url, _title_words(title)))
    return links


def linkify_linkedin_draft(li_content: str, content: str, draft: dict | None = None) -> str:
    """Hyperlink bolded headlines in the LinkedIn draft using source links
    already present in this week's technical post, plus the raw source
    titles/URLs from this week's draft if provided (see _draft_links).

    Skips section headers (the three anchor emoji), short/all-caps bold runs,
    and anything already a markdown link. Never invents a URL — a headline
    with no confident match is left as plain bold text.
    """
    links = extract_post_links(content)
    if draft:
        links = links + _draft_links(draft)
    if not links:
        return li_content

    def replace_bold(match):
        inner = match.group(1)
        if inner.startswith("[") or any(e in inner for e in ("⚡", "👀", "🛠️")):
            return match.group(0)
        if inner.isupper() or len(inner) < 10:
            return match.group(0)
        trailing_colon = inner.rstrip().endswith(":")
        title_part = inner.rstrip(":").strip() if trailing_colon else inner.strip()
        url = _best_link_match(title_part, links)
        if url:
            suffix = ":" if trailing_colon else ""
            return f"**[{title_part}]({url}){suffix}**"
        return match.group(0)

    return re.sub(r"\*\*([^*]+)\*\*", replace_bold, li_content)


# [^\n]* tolerates trailing words after "Top 5" (e.g. the older "Top 5 This
# Week" heading used through 2026-07-28) — the SYSTEM_PROMPT now pins the
# heading to exactly "## Top 5" going forward, but this stays tolerant in
# case of future drift, since a silent empty match here quietly regresses
# both the Newsletter draft and the announcement post back to re-deriving
# their own Top 5 instead of using the human-reviewed one. See cf9c8bf and
# the 2026-08-04 regression this tolerance was added to fix.
# Terminates on the next "## " heading rather than a "---" divider: the
# 2026-08-04 post dropped the "---" section dividers between category
# headings entirely (confirmed via git history — earlier posts had them,
# that one doesn't), so a "---"-anchored terminator silently matched zero
# items on that post even after the heading-text fix above. re.MULTILINE
# lets the lookahead's ^ match "## " at the start of any line, not just
# the start of the string.
_TOP5_SECTION_RE = re.compile(r"^## Top 5[^\n]*\n(.*?)(?=\n^## |\Z)", re.DOTALL | re.MULTILINE)
_TOP5_ITEM_RE = re.compile(
    # The optional non-capturing group tolerates the {{< cat "..." >}} shortcode
    # tag_top5_categories() inserts right after the title — present on posts
    # generated after that function existed, absent on older ones.
    #
    # The terminating lookahead used to require a BLANK line before the next
    # numbered item (\n\n\d+\.\s+\*\*), matching the SYSTEM_PROMPT's formatting
    # rule ("each numbered item is followed by a blank line"). Confirmed live
    # 2026-08-25: the model doesn't always follow that formatting rule, and
    # when it emits Top 5 items back-to-back with no blank line between them,
    # the old lookahead never found its boundary until \Z — collapsing all 5
    # items into a single match (item 1's title, with items 2-5 swallowed
    # into its body) and silently starving extract_top5()/the announcement
    # post of the other 4 items. \s* tolerates zero, one, or many newlines
    # between items, so this works whether or not the blank-line rule was
    # actually followed that week.
    r"^\d+\.\s+\*\*(?P<title>.+?)\*\*(?:\{\{<\s*cat\s+\"[^\"]*\"\s*>\}\})?\s*-?\s*(?P<body>.+?)(?=\n\s*\d+\.\s+\*\*|\Z)",
    re.MULTILINE | re.DOTALL,
)


def extract_top5(post_content: str) -> list[dict]:
    """Pull the technical post's own Top 5 items (title + explanation).

    This is what already went through editorial review (Step 2 of the
    weekly workflow — "Top 5 ranking, reorder if your judgment disagrees").
    The LinkedIn edition should be grounded in this same ranking, not
    re-derive its own — see build_linkedin_prompt() for why.
    """
    section_match = _TOP5_SECTION_RE.search(post_content)
    if not section_match:
        return []
    items = []
    for m in _TOP5_ITEM_RE.finditer(section_match.group(1)):
        items.append({"title": m.group("title").strip(), "body": " ".join(m.group("body").split())})
    return items


# ── Author byline hints for the LinkedIn draft ──────────────────────────────
# scraper.py's fetch_rss() now captures a per-item author (feedparser's
# entry.author, mapped from RSS dc:creator / Atom author). Coverage varies:
# TechCommunity blogs return a bare username (e.g. "ScottSawyer", no space —
# not a display name, and not something a reader would recognize), WordPress-
# hosted blogs like Microsoft Security Blog return a real "First Last" name,
# and structured feeds with no individual byline (Roadmap, likely MSRC/
# Mechanics) return None. Only the "First Last" case is safe to surface in
# LinkedIn body text — a bare username reads as sloppy and may not even be
# the person's real name.
def _is_full_name(author: str | None) -> bool:
    """True only for a real 'First Last'-shaped individual, never a bare
    TechCommunity username, None, or an org/channel byline that happens to
    look like a two-word name. Confirmed live 2026-08-18: the plain
    len(parts) >= 2 check alone flagged "Microsoft Mechanics" (a YouTube
    channel byline, not a person) and "Microsoft Security Research and
    Srinivasan Govindarajan" (a team-plus-person compound byline) as safe
    to credit inline, which they aren't. Rejecting any author string that
    contains the word "Microsoft" catches both cases, since a real
    individual's byline never includes the company name itself. This is a
    narrow, targeted rejection, not a broader org-name denylist, since a
    compound byline like the Security Research one still deserves manual
    review (the real name inside it, e.g. Srinivasan Govindarajan, is
    worth crediting once someone pulls it out by hand) rather than being
    silently dropped from the candidates list entirely.
    """
    if not author:
        return False
    parts = author.strip().split()
    if len(parts) < 2 or not all(p.replace("-", "").isalpha() for p in parts):
        return False
    if any(p.lower() == "microsoft" for p in parts):
        return False
    return True


def _best_author_match(headline: str, items: list[dict], min_overlap: float = 0.6) -> str | None:
    """Find the original scraped item whose title best overlaps a Top 5
    headline and return its author if it's a real full name.

    A Top 5 headline is Claude's reworded version of the original item
    title, not a literal match, so this reuses the same overlap-coefficient
    approach as _best_link_match() (see that docstring for why overlap over
    the smaller word-set beats Jaccard for "same story, reworded" matching)
    rather than an exact title lookup.
    """
    headline_words = _title_words(headline)
    if not headline_words:
        return None
    best_author, best_score = None, 0.0
    for item in items:
        author = item.get("author")
        if not _is_full_name(author):
            continue
        title_words = _title_words(item.get("title", ""))
        if not title_words:
            continue
        shared = headline_words & title_words
        smaller = min(len(headline_words), len(title_words))
        if smaller < 2 and headline_words != title_words:
            continue
        score = len(shared) / smaller
        if score > best_score:
            best_score, best_author = score, author
    return best_author if best_score >= min_overlap else None


def build_linkedin_prompt(draft: dict, week_of: str, post_content: str, max_age_days: int = MAX_AGE_DAYS) -> str:
    """Build a compact digest summary to feed the LinkedIn draft.

    Freshness filtering (--max-age-days) previously fixed the LinkedIn
    edition citing much older stories than the technical post, but a
    second, subtler divergence remained: TOP 5 was independently
    re-derived by the LinkedIn-drafting call from the full raw item pool
    (draft["grouped_items"]), not from the technical post's own Top 5 —
    so the two could legitimately disagree on which 5 items matter most,
    or the LinkedIn edition could headline something that didn't even
    make it into this week's published post. Confirmed 2026-07-21: 3 of
    the LinkedIn draft's 5 items (including the hook-line lead story)
    were absent from the actual published post anywhere — Top 5, category
    sections, Action Required, or sources.
    Now the technical post's Top 5 (already human-reviewed) is passed in
    as a required, non-negotiable list; only WORTH YOUR ATTENTION and ONE
    FOR THE HELP DESK still draw from the wider freshness-filtered pool,
    since those are meant to surface extra items beyond the Top 5.
    """
    top5 = extract_top5(post_content)
    all_items = [it for items in draft.get("grouped_items", {}).values() for it in items]
    lines = []
    if top5:
        lines.append(
            "CONFIRMED TOP 5 (already reviewed and published in this week's "
            "technical post — use exactly these 5 items, in this order, "
            "reworded for LinkedIn voice and length. Do not substitute, "
            "add, drop, or reorder them, and do not pull a different item "
            "from below into TOP 5). A trailing [byline: Name] is the "
            "confirmed real author of that source post — safe to credit by "
            "name per the system prompt's rule; items with no [byline: ...] "
            "tag have no confirmed individual author, so don't invent one:"
        )
        for i, item in enumerate(top5, 1):
            author = _best_author_match(item["title"], all_items)
            byline = f" [byline: {author}]" if author else ""
            lines.append(f"  {i}. {item['title']}: {item['body'][:300]}{byline}")
        lines.append("")
        lines.append(
            "ADDITIONAL ITEMS (pool for WORTH YOUR ATTENTION and ONE FOR "
            "THE HELP DESK only — never for TOP 5):"
        )

    for cat, items in draft.get("grouped_items", {}).items():
        # Exec-only content (see build_prompt) — no place in the LinkedIn edition either.
        if cat == "Research & Trends":
            continue
        fresh_items = filter_recent(items, max_age_days=max_age_days)
        if not fresh_items:
            continue
        lines.append(f"[{cat}]")
        for item in fresh_items:
            byline = f" [byline: {item['author']}]" if _is_full_name(item.get("author")) else ""
            lines.append(f"  - {item['title']}: {(item.get('body') or '')[:200]}{byline}")
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


# ── LinkedIn tag candidates ──────────────────────────────────────────────────
TAG_CANDIDATES_FILE = STATE_DIR / "tag_candidates.json"


def collect_tag_candidates(top5: list[dict], draft: dict) -> list[dict]:
    """Surface every author on this week's item pool as a manual @-tag
    candidate for LinkedIn — editorial-review-only, never embedded in the
    generated post body.

    This can't produce a real, working @-mention automatically: LinkedIn
    only resolves a mention to a member's URN through its own UI
    autocomplete (or the API with that ID already known), neither of which
    an RSS-scraped author name gives us. What this can do is hand Ryan a
    short "who to search for and tag" list alongside the draft, so it's a
    copy/paste in the LinkedIn composer instead of re-reading every source
    link by hand.

    Includes bare TechCommunity usernames (e.g. "ScottSawyer") as well as
    real full names — is_full_name flags which is which. Only full names
    are safe to credit inline in the LinkedIn draft body itself (see
    _is_full_name()), but a username still tells Ryan who to look up.
    """
    all_items = [it for items in draft.get("grouped_items", {}).values() for it in items]
    seen = set()
    candidates = []

    # Top 5 items: match by headline overlap (same approach as the byline
    # hints in build_linkedin_prompt), but don't require a full name here —
    # a bare username is still useful in a review-only list.
    for item in top5:
        headline_words = _title_words(item["title"])
        if not headline_words:
            continue
        best_item, best_score = None, 0.0
        for it in all_items:
            if not it.get("author"):
                continue
            title_words = _title_words(it.get("title", ""))
            if not title_words:
                continue
            shared = headline_words & title_words
            smaller = min(len(headline_words), len(title_words))
            if smaller < 2 and headline_words != title_words:
                continue
            score = len(shared) / smaller
            if score > best_score:
                best_score, best_item = score, it
        if best_item and best_score >= 0.6:
            key = (best_item["author"], best_item.get("url"))
            if key not in seen:
                seen.add(key)
                candidates.append({
                    "item_title": best_item["title"],
                    "author": best_item["author"],
                    "is_full_name": _is_full_name(best_item["author"]),
                    "source": best_item.get("source", ""),
                    "url": best_item.get("url", ""),
                    "section": "Top 5",
                })

    # Everything else in this week's pool with an author — in case something
    # worth crediting landed in Worth Your Attention / Help Desk instead.
    for it in all_items:
        author = it.get("author")
        if not author:
            continue
        key = (author, it.get("url"))
        if key in seen:
            continue
        seen.add(key)
        candidates.append({
            "item_title": it.get("title", ""),
            "author": author,
            "is_full_name": _is_full_name(author),
            "source": it.get("source", ""),
            "url": it.get("url", ""),
            "section": "pool",
        })
    return candidates


def write_tag_candidates(candidates: list[dict], week_of: str) -> Path:
    STATE_DIR.mkdir(exist_ok=True)
    with open(TAG_CANDIDATES_FILE, "w") as f:
        json.dump(
            {
                "week_of": week_of,
                "generated": datetime.now(timezone.utc).date().isoformat(),
                "candidates": candidates,
            },
            f,
            indent=2,
        )
    return TAG_CANDIDATES_FILE


def write_linkedin_draft(content: str, week_of: str) -> Path:
    path = STATE_DIR / f"linkedin_draft_{week_of}.txt"
    path.write_text(content, encoding="utf-8")
    log.info(f"LinkedIn draft written → {path}")
    return path


def build_announcement_prompt(top5: list[dict], week_of: str) -> str:
    """Build the prompt for the short native-post teaser (see
    ANNOUNCEMENT_SYSTEM_PROMPT for why this is a separate, deliberately
    thinner draft from the Newsletter edition).

    Reuses the same human-reviewed Top 5 the Newsletter draft is grounded
    in (extract_top5() on the technical post) rather than re-deriving its
    own — see build_linkedin_prompt()'s docstring for why that matters.
    """
    lines = [f"  {i}. {item['title']}" for i, item in enumerate(top5, 1)]
    return ANNOUNCEMENT_PROMPT_TEMPLATE.format(
        week_of=week_of,
        top5_lines="\n".join(lines),
    )


def call_claude_announcement(prompt: str) -> str:
    client = anthropic.Anthropic()
    log.info("Calling Claude API for LinkedIn announcement post...")
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=ANNOUNCEMENT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def write_announcement_draft(content: str, week_of: str) -> Path:
    path = STATE_DIR / f"linkedin_post_{week_of}.txt"
    path.write_text(content, encoding="utf-8")
    log.info(f"LinkedIn announcement draft written → {path}")
    return path


def call_claude_exec(prompt: str) -> str:
    client = anthropic.Anthropic()
    log.info("Calling Claude API for Executive's Guide...")
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
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


PUBLISH_GAP_WARN_DAYS = 10

def check_publish_gap(current_week_of: str, threshold_days: int = PUBLISH_GAP_WARN_DAYS):
    """Warn loudly if it's been unusually long since the last published post.

    Normal Tuesday cadence means at most ~7-8 days between posts. A bigger
    gap is the earliest possible signal that a weekly run was skipped,
    delayed, or silently failed somewhere upstream — this is exactly what
    happened 2026-07-17 to 2026-07-21: production drift blocked git pulls
    for weeks with no error anywhere, so 07-08 through 07-13 content that
    should have gone out in the 07-14 digest sat unconsumed, aged past the
    7-day freshness window, and produced a near-empty CVE-only digest by
    the time 07-21 ran. See MAINTENANCE.md.

    Catching the gap *here*, at the moment a new digest is about to
    publish, surfaces it immediately in the run's own log/summary — instead
    of relying on someone noticing a thin-looking live page days later and
    reverse-engineering the cause after the fact.
    """
    existing_dates = sorted(
        p.stem for p in POSTS_DIR.glob("????-??-??.md") if p.stem != current_week_of
    )
    if not existing_dates:
        return None
    try:
        last_date = datetime.strptime(existing_dates[-1], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        current_date = datetime.strptime(current_week_of, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    gap_days = (current_date - last_date).days
    if gap_days > threshold_days:
        log.warning(
            f"⚠️  {gap_days} days since the last published digest ({existing_dates[-1]}) — "
            f"expected ~7. A run may have been skipped or delayed upstream (check git status "
            f"on the LXC — see MAINTENANCE.md's 'Site changes pushed but not appearing live'). "
            f"Consider whether this week's draft has a stale backlog needing --max-age-days "
            f"before treating a thin section as a genuinely quiet week."
        )
        return gap_days
    return None


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

    max_age_days = args.max_age_days if args.max_age_days else MAX_AGE_DAYS
    if args.max_age_days:
        log.info(f"Freshness window overridden to {max_age_days} days (default is {MAX_AGE_DAYS}) via --max-age-days")
    publish_gap_days = check_publish_gap(week_of)
    prompt = build_prompt(draft, max_age_days=max_age_days)
    deadline_candidates = detect_deadline_candidates(draft)

    if args.dry_run:
        print("\n" + "="*60)
        print("SYSTEM PROMPT:")
        print(SYSTEM_PROMPT)
        print("\nUSER PROMPT:")
        print(prompt[:2000] + "..." if len(prompt) > 2000 else prompt)
        print("="*60)
        if deadline_candidates:
            print(f"\nKey Date candidates ({len(deadline_candidates)}):")
            for c in deadline_candidates:
                tag = " [structured — Roadmap-confirmed]" if c.get("structured") else ""
                print(f"  - [{c['pillar']}] {c['title']} — signal: '{c['signal']}', date: {c['extracted_date']}, "
                      f"suggested type: {c.get('suggested_type', 'feature')}{tag}")
        else:
            print("\nKey Date candidates: none flagged this week.")
        log.info("Dry run complete — no API call made.")
        return

    content = clean_dashes(call_claude(prompt))
    content = tag_top5_categories(content)
    content = inject_card_stats(content)
    validate_all_cves_in_action_required(content)
    check_emphasis_tags(content, week_of)
    post_path = write_post(content, week_of)

    # Generate Executive's Guide unless skipped
    exec_post_path = None
    if not args.skip_exec:
        try:
            exec_prompt = build_exec_prompt(draft, max_age_days=max_age_days)
            exec_content = clean_dashes(call_claude_exec(exec_prompt))
            exec_content = inject_exec_risk_stats(exec_content)
            check_emphasis_tags(exec_content, f"{week_of}-exec")
            exec_post_path = write_exec_post(exec_content, week_of)
        except Exception as e:
            log.warning(f"Executive's Guide generation failed (non-fatal): {e}")

    # Generate LinkedIn newsletter draft unless skipped
    linkedin_draft_path = None
    if not args.skip_linkedin:
        try:
            li_prompt = build_linkedin_prompt(draft, week_of, content, max_age_days=max_age_days)
            li_content = clean_dashes(call_claude_linkedin(li_prompt))
            # No hashtags here — this is the long-form newsletter article body,
            # pasted into LinkedIn's Newsletter editor, where hashtags aren't
            # functional/linkable. build_hashtags()/TAG_HASHTAGS are used below,
            # on the separate short announcement/teaser post — see
            # feedback_linkedin_hashtags memory.
            li_content = linkify_linkedin_draft(li_content, content, draft)
            linkedin_draft_path = write_linkedin_draft(li_content, week_of)
        except Exception as e:
            log.warning(f"LinkedIn draft generation failed (non-fatal): {e}")

    # Generate the short announcement/teaser post unless skipped. Separate
    # try/except from the Newsletter draft above so one failing doesn't take
    # down the other.
    announcement_path = None
    if not args.skip_linkedin:
        try:
            top5 = extract_top5(content)
            ann_prompt = build_announcement_prompt(top5, week_of)
            ann_content = clean_dashes(call_claude_announcement(ann_prompt))
            tags = extract_post_tags(content)
            hashtags = " ".join(build_hashtags(tags))
            post_url = modernworkweekly_url(f"posts/{week_of}")
            ann_content = (
                f"{ann_content}\n\n{hashtags}\n\n"
                f"[Post this first. Immediately after it publishes, add this as the "
                f"FIRST comment — do not put it in the body, do not add a second link: "
                f"{post_url}]"
            )
            announcement_path = write_announcement_draft(ann_content, week_of)
        except Exception as e:
            log.warning(f"LinkedIn announcement post generation failed (non-fatal): {e}")

    # Author tag candidates for manual LinkedIn @-tagging — see
    # collect_tag_candidates() for why this can't be a real embedded mention.
    tag_candidates = []
    tag_candidates_path = None
    if not args.skip_linkedin:
        try:
            tag_candidates = collect_tag_candidates(extract_top5(content), draft)
            if tag_candidates:
                tag_candidates_path = write_tag_candidates(tag_candidates, week_of)
        except Exception as e:
            log.warning(f"Tag-candidate collection failed (non-fatal): {e}")

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

    candidates_path = write_deadline_candidates(deadline_candidates)

    print(f"\n{'='*60}")
    print(f"  Digest drafted:      {post_path}")
    if exec_post_path:
        print(f"  Executive's Guide:   {exec_post_path}")
    if linkedin_draft_path:
        print(f"  LinkedIn draft:      {linkedin_draft_path}")
    if announcement_path:
        print(f"  LinkedIn post:       {announcement_path}")
    if tag_candidates:
        full_name_count = sum(1 for c in tag_candidates if c["is_full_name"])
        print(f"  Tag candidates:      {len(tag_candidates)} author(s) ({full_name_count} full name, "
              f"{len(tag_candidates) - full_name_count} username-only) → {tag_candidates_path}")
    if deadline_candidates:
        print(f"  Key Date candidates: {len(deadline_candidates)} flagged for review → {candidates_path}")
    else:
        print(f"  Key Date candidates: none flagged this week")
    if publish_gap_days:
        print(f"  ⚠️  PUBLISH GAP:      {publish_gap_days} days since the last digest (expected ~7) — a run may")
        print(f"                       have been skipped/delayed upstream. See the log warning above.")
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
                        help="Skip LinkedIn newsletter draft and announcement post generation")
    parser.add_argument("--max-age-days", type=int, default=None,
                        help=f"Override the freshness window (default {MAX_AGE_DAYS} days) for this run only. "
                             f"Use for a one-off regeneration when a real backlog built up "
                             f"(e.g. after a deploy/pull outage delayed a normal week's publish) — "
                             f"don't use this to permanently loosen filtering.")
    args = parser.parse_args()
    run(args)
