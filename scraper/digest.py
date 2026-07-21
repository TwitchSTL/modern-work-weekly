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
- Section order must be: Top 5 → pillar category sections (Identity & Access, Endpoint & Device Management, Collaboration & Productivity, AI & Copilot, Employee Experience, Security & Compliance) → Action Required → sources front matter. Do NOT place Action Required before the category sections.
- Action Required section: ALWAYS include this section — never omit it. Include any items with deadlines, required admin steps, patch obligations, CVE mitigations, governance decisions, or deprecation timelines. Use the same bullet format as category sections, with the deadline date or urgency called out prominently at the start of the description. If nothing is strictly time-sensitive this week, include the 2-3 items that most warrant an engineer's attention in the next 30 days.
- List all source URLs in the YAML front matter under a `sources:` key as a YAML list. Do NOT include a {{< sources >}} shortcode in the post body.

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
- Front matter: title (must be exactly "Executive's Guide — Week of YYYY-MM-DD"), date, description (1-2 sentences on the week's business significance — not technical), categories: ["Executive Guide"], tags (business-level: compliance, security, cost, user-impact, licensing, identity, devices, data-protection)
- ## The Week at a Glance — 3-4 risk-labeled bullets in plain English
- ## Why This Week Matters — 2-3 sentences of leadership-level context; the one thing leadership must understand
- ## What Microsoft's Research Is Saying — OPTIONAL. Include only when "Research & Trends" items are present in the raw data; omit the entire section, heading included, if there are none this week. 1-3 bullets translating Microsoft's own workplace/AI research (Viva/WorkLab research essays) into what it means for this organization's planning. This is context, not an action item, so do not add it to Risk & Compliance or Planning Horizon.
- ## Risk & Compliance — markdown table with columns: Change | Business Risk | Regulatory Angle | Act By
- ## What Your Employees Will Notice — bullets of user-facing changes; what to communicate proactively
- ## What Your Help Desk Should Expect — specific ticket types or support volume changes to anticipate
- ## Cost & Licensing — licensing tier implications, new costs, or spend optimization opportunities (omit section if nothing applies)
- ## Planning Horizon — deadlines in the next 30/60/90 days requiring leadership decisions, budget approval, or vendor coordination
- ## If You Take No Action — plain-language consequences for the 2-3 highest-risk items only

Regulatory angles to surface where relevant: HIPAA, SOC 2, CMMC, FedRAMP, NIST CSF, cyber insurance requirements, GDPR, state privacy laws.

Strategic framing: when a change affects identity, device, or network access controls, frame its significance in Zero Trust maturity terms where it helps leadership understand posture, e.g. "closes an implicit-trust gap," "strengthens least-privilege enforcement," "extends verification to a previously trusted zone." This is a strategy lens for identity/device/network/security items specifically, used where it adds insight, not a label to attach to every row. Collaboration, AI/Copilot, and employee-experience items don't need it.

Source citations — REQUIRED. Executives trust named references, not raw URLs:
- At the end of EVERY section (including Risk & Compliance, Planning Horizon, and If You Take No Action), you MUST include a line formatted exactly as:
  `*Sources: [Descriptive Name](url) · [Descriptive Name](url)*`
- Use 1–3 sources per section, drawn from the raw data URLs. Name them meaningfully: "Microsoft Threat Intelligence", "Entra What's New", "M365 Roadmap", "Intune What's New", "Microsoft Security Blog", "Intune What's New", "Purview What's New", etc. Never paste a raw URL as the link text.
- In the Risk & Compliance table, hyperlink the item name in the Change column to its source URL: e.g. **[Storm-2949 breach via stolen identity](url)**
- In the Planning Horizon table, hyperlink the item name in the Item column to its source URL where available.
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
1. Title — format exactly as: "Modern Work Weekly — Week of YYYY-MM-DD" (this goes in the LinkedIn article title field, output it on its own line prefixed with "TITLE: ")
2. Hook line — one punchy sentence that names the biggest story this week. No greeting, no "this week in M365". Just the hook.
3. **⚡ TOP 5 THIS WEEK** — the 5 most important changes, numbered, one line each, blank line after each. Bold the item title, then a colon, then the explanation. Format: "1. **Item title:** explanation."
4. **👀 WORTH YOUR ATTENTION** — 2–3 items that aren't urgent but signal where things are heading. One sentence each, dash-prefixed.
5. **🛠️ ONE FOR THE HELP DESK** (optional) — a single change that's going to generate tickets or questions. Skip if nothing fits.
6. Closing line — one sentence pointing to the full digest. Format: "Full digest with sources and admin actions - link in the comments." Do not include a URL in this line - the URL gets posted separately as the first comment after publishing, to avoid LinkedIn's reach penalty on posts with outbound links in the body.

Do not include any hashtags in your output. Hashtags are appended automatically after generation, derived from the tags already assigned to this week's technical post — do not invent your own. Do not add a sign-off. Do not wrap output in code fences.

Do not include hyperlinks or Markdown link syntax (no `[text](url)`) anywhere in the output — write plain bolded headline text only, e.g. "**Item title:**". Source links for each item are added automatically after generation by matching your headlines against the links already present in this week's technical post — inventing your own URL here would risk linking to the wrong (or a nonexistent) page.

Style: Never use em dashes. Use a comma, a colon, a semicolon, or split into two separate sentences instead. Also avoid the contrastive construction "X isn't Y, it's Z" and its variants ("This isn't..., it's...", "That isn't..., it's..."); state the point directly instead of setting up a false contrast first.

Language: American English throughout. Use American spellings — "organization" not "organisation", "behavior" not "behaviour", "license" not "licence", "customize" not "customise", etc."""

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


def detect_deadline_candidates(draft: dict) -> list[dict]:
    """Scan this week's accumulated items for retirement/deprecation/GA-date
    language so nothing dated silently misses site/data/deadlines.json.

    Returns a list of {title, url, source, pillar, signal, extracted_date}.
    extracted_date is the raw matched text (e.g. "August 2026") or None if a
    retirement/deprecation signal hit but no date-like text was found nearby
    — those still get surfaced as a "watch for a date" item rather than
    dropped, since Microsoft often confirms the direction before the date.
    """
    candidates = []
    for cat, items in draft.get("grouped_items", {}).items():
        for item in items:
            text = f"{item.get('title', '')} {item.get('body', '')}"
            text_lower = text.lower()
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
            })
    return candidates


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
    # comparison — see dateutils.py), then cap at 8 items per category, most
    # recent first, to keep input within model limits. With 6 pillars × 8
    # items the prompt stays well under 8k input tokens.
    #
    # max_age_days defaults to the standard 7-day window but can be widened
    # via --max-age-days for a one-off regeneration when a real backlog has
    # built up (e.g. 2026-07-21: production drift meant several genuinely
    # new items from 07-08 through 07-13 never got consumed by the 07-14
    # run, and by the time 07-21 ran they'd aged past 7 days). Don't lower
    # the module-level MAX_AGE_DAYS default to "fix" a one-time backlog —
    # that filter is what stops stale multi-week content from flooding a
    # normal week.
    MAX_PER_CAT = 8
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
            }
            for item in sorted_items[:MAX_PER_CAT]
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


def build_linkedin_prompt(draft: dict, week_of: str, max_age_days: int = MAX_AGE_DAYS) -> str:
    """Build a compact digest summary to feed the LinkedIn draft.

    This previously had zero recency filtering — every item ever
    accumulated in pending_draft.json was dumped into the prompt with no
    date signal at all, which is why the LinkedIn edition could end up
    citing entirely different (and much older) stories than the technical
    post: it was drawing from a far larger, completely unfiltered pool.
    Apply the same freshness gate used everywhere else (same --max-age-days
    override as build_prompt() / build_exec_prompt()).
    """
    lines = []
    for cat, items in draft.get("grouped_items", {}).items():
        # Exec-only content (see build_prompt) — no place in the LinkedIn edition either.
        if cat == "Research & Trends":
            continue
        fresh_items = filter_recent(items, max_age_days=max_age_days)
        if not fresh_items:
            continue
        lines.append(f"[{cat}]")
        for item in fresh_items:
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
                print(f"  - [{c['pillar']}] {c['title']} — signal: '{c['signal']}', date: {c['extracted_date']}")
        else:
            print("\nKey Date candidates: none flagged this week.")
        log.info("Dry run complete — no API call made.")
        return

    content = call_claude(prompt)
    post_path = write_post(content, week_of)

    # Generate Executive's Guide unless skipped
    exec_post_path = None
    if not args.skip_exec:
        try:
            exec_prompt = build_exec_prompt(draft, max_age_days=max_age_days)
            exec_content = call_claude_exec(exec_prompt)
            exec_post_path = write_exec_post(exec_content, week_of)
        except Exception as e:
            log.warning(f"Executive's Guide generation failed (non-fatal): {e}")

    # Generate LinkedIn newsletter draft unless skipped
    linkedin_draft_path = None
    if not args.skip_linkedin:
        try:
            li_prompt = build_linkedin_prompt(draft, week_of, max_age_days=max_age_days)
            li_content = call_claude_linkedin(li_prompt)
            li_content = linkify_linkedin_draft(li_content, content, draft)
            hashtags = build_hashtags(extract_post_tags(content))
            li_content = li_content.rstrip() + "\n\n" + " ".join(hashtags)
            if len(hashtags) <= 1:
                log.warning("No matching content tags found for hashtag compilation — only the brand hashtag was included.")
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

    candidates_path = write_deadline_candidates(deadline_candidates)

    print(f"\n{'='*60}")
    print(f"  Digest drafted:      {post_path}")
    if exec_post_path:
        print(f"  Executive's Guide:   {exec_post_path}")
    if linkedin_draft_path:
        print(f"  LinkedIn draft:      {linkedin_draft_path}")
    if deadline_candidates:
        print(f"  Key Date candidates: {len(deadline_candidates)} flagged for review → {candidates_path}")
    else:
        print(f"  Key Date candidates: none flagged this week")
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
    parser.add_argument("--max-age-days", type=int, default=None,
                        help=f"Override the freshness window (default {MAX_AGE_DAYS} days) for this run only. "
                             f"Use for a one-off regeneration when a real backlog built up "
                             f"(e.g. after a deploy/pull outage delayed a normal week's publish) — "
                             f"don't use this to permanently loosen filtering.")
    args = parser.parse_args()
    run(args)
