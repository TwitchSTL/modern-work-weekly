#!/usr/bin/env python3
"""
scraper.py — Modern Work Weekly scraper.

Fetches Microsoft portal update pages, extracts new items since last run,
deduplicates against seen_items.json, and writes a structured JSON draft
for review in Claude.ai.

Usage:
    python scraper.py                    # Normal weekly run
    python scraper.py --force-all        # Ignore seen_items, pull everything
    python scraper.py --source Intune    # Single source only
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup

from sources import SOURCES, CLASSIFICATION_KEYWORDS, PHASE_KEYWORDS, DEFAULT_CATEGORY
from dateutils import item_age_days

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
STATE_FILE = STATE_DIR / "seen_items.json"
PENDING_DRAFT_FILE = STATE_DIR / "pending_draft.json"
LOG_DIR = BASE_DIR / "logs"
HEALTH_DATA_FILE = BASE_DIR / "site" / "data" / "health.json"
HEALTH_BASELINE_FILE = STATE_DIR / "health_baseline.json"
POSTS_DIR = BASE_DIR / "site" / "content" / "posts"

STATE_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
(BASE_DIR / "site" / "data").mkdir(parents=True, exist_ok=True)

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / f"scraper_{datetime.now().strftime('%Y%m%d')}.log"),
    ],
)
log = logging.getLogger(__name__)

# ── HTTP session ─────────────────────────────────────────────────────────────
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "ModernWorkWeekly/1.0 (blog scraper; contact via GitHub)",
    "Accept-Language": "en-US,en;q=0.9",
})
REQUEST_DELAY = 2  # seconds between requests — be polite

# An item that's never been scraped before (new source, or a low-volume feed
# whose "latest 15 entries" reach back months) still carries its real,
# possibly old, publish date. digest.py applies a tighter 7-day freshness
# filter at draft-build time regardless, but without a backstop here,
# genuinely dead items (confirmed examples: Oct 2025, Nov 2025 posts) sit in
# pending_draft.json indefinitely, growing the backlog for no reason. This is
# deliberately looser than digest.py's filter to tolerate irregular cron
# cadence between digest publishes.
MAX_PENDING_AGE_DAYS = 21


def load_published_urls(posts_dir: Path) -> set[str]:
    """Collect every source URL already published in a prior post's category
    sections (Identity & Access, Endpoint & Device Management, Collaboration
    & Productivity, AI & Copilot, Employee Experience, Security & Compliance).

    This is a backstop against seen_items.json losing entries between runs —
    it's gitignored and lives only on the LXC, so it has no second copy to
    recover from if it gets corrupted or written inconsistently. The post
    archive in site/content/posts/ is git-tracked and can't silently revert,
    so cross-checking against it catches anything the primary seen_ids check
    misses.

    Deliberately excludes 'Top 5' and 'Action Required' sections: those
    intentionally re-list still-unresolved high-priority items week over
    week with freshly-written prose and updated urgency framing. That
    recurrence is by design, not a duplicate-content bug, so URLs that only
    ever appear there must not be treated as permanently "published."
    """
    urls: set[str] = set()
    if not posts_dir.exists():
        return urls
    url_re = re.compile(r'https?://\S+')
    for md_file in posts_dir.glob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        parts = text.split("---", 2)
        body = parts[2] if len(parts) >= 3 else text
        sections = re.split(r'(?m)^## ', body)
        kept = []
        for section in sections:
            heading = section.split("\n", 1)[0].strip().lower()
            if heading.startswith("top 5") or heading.startswith("action required"):
                continue
            kept.append(section)
        category_body = "\n".join(kept)
        for match in url_re.findall(category_body):
            cleaned = match.rstrip(")]}>,.'\"*`").split("#")[0]
            urls.add(cleaned)
    return urls


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"seen_ids": [], "last_run": None, "total_items_seen": 0}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    log.info(f"State saved — {len(state['seen_ids'])} items tracked total.")


def item_id(source_name: str, title: str) -> str:
    """Stable hash ID for deduplication."""
    raw = f"{source_name}::{title.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def classify_item(title: str, body: str) -> tuple[str, bool]:
    """Classify an item into a category based on keyword matching.

    Returns (category, matched). matched=False means no keyword scored above
    zero and the category is DEFAULT_CATEGORY — a guess, not a real signal.
    Callers should track this rather than treat every item as equally
    confident; see write_classification_stats().
    """
    combined = (title + " " + body).lower()
    scores = {cat: 0 for cat in CLASSIFICATION_KEYWORDS}
    for cat, keywords in CLASSIFICATION_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                scores[cat] += 1
    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best, True
    return DEFAULT_CATEGORY, False


def detect_phase(title: str, body: str) -> str:
    """Detect rollout phase from text."""
    combined = (title + " " + body).lower()
    for phase, keywords in PHASE_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                return phase
    return "GA"


def detect_admin_action(body: str) -> str | None:
    """Detect if admin action is required."""
    action_phrases = [
        "required action", "action required", "you must", "admins must",
        "you should", "migrate before", "update before", "opt out",
        "review your", "transition away", "take action",
    ]
    body_lower = body.lower()
    for phrase in action_phrases:
        if phrase in body_lower:
            sentences = body.split(". ")
            for s in sentences:
                if phrase in s.lower():
                    return s.strip()[:200]
    return None


def fetch_rss(source: dict) -> list[dict]:
    """Fetch items from an RSS/Atom feed."""
    log.info(f"  RSS → {source['name']}")
    feed = feedparser.parse(source["rss"])
    items = []
    for entry in feed.entries[:15]:
        title = entry.get("title", "").strip()
        body = BeautifulSoup(
            entry.get("summary", entry.get("description", "")), "html.parser"
        ).get_text(separator=" ", strip=True)[:800]
        # feedparser normalizes the publish date into a UTC struct_time at
        # published_parsed regardless of the feed's original date format
        # (RFC 822, ISO 8601, the M365 Roadmap feed's non-standard " Z"
        # suffix, etc.) — prefer that over the raw string so every item
        # written to pending_draft.json carries one consistent, directly
        # comparable date format instead of whatever format that particular
        # feed happened to use.
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if source.get("no_item_dates"):
            # This feed doesn't carry a real per-item date — recording None
            # (rather than falling back to "now") lets item_age_days() report
            # unknown age honestly, so downstream freshness filters keep the
            # item instead of either wrongly aging it out or wrongly treating
            # a scrape-time stamp as if it were a real publish date.
            date_str = None
        elif parsed:
            date_str = datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()
        else:
            date_str = entry.get(
                "published", entry.get("updated", datetime.now(timezone.utc).isoformat())
            )
        items.append({
            "source": source["name"],
            "title": title,
            "body": body,
            "url": entry.get("link", source["url"]),
            "date": date_str,
        })
    return items


def fetch_json_status(source: dict) -> list[dict]:
    """Fetch items from a JSON status API (e.g. status.office365.com/api/messages).

    The rss field holds the JSON endpoint URL. Field names vary by API — this
    handler tries common patterns defensively.
    """
    log.info(f"  JSON API → {source['name']}")
    try:
        resp = SESSION.get(source["rss"], timeout=15)
        resp.raise_for_status()
        if not resp.content.strip():
            log.info(f"    {source['name']} returned empty body — no active incidents.")
            return []
        data = resp.json()
    except (json.JSONDecodeError, ValueError):
        # Non-JSON response (e.g. empty-ish body, HTML error page) — treat as no incidents
        log.info(f"    {source['name']} returned non-JSON response — no active incidents.")
        return []
    except Exception as e:
        log.warning(f"    Failed to fetch {source['name']}: {e}")
        return []

    # Unwrap envelope if needed
    if isinstance(data, dict):
        data = data.get("messages") or data.get("value") or data.get("items") or []

    if not isinstance(data, list):
        log.warning(f"    Unexpected JSON shape from {source['name']} — expected list, got {type(data).__name__}")
        return []

    items = []
    for msg in data[:15]:
        if not isinstance(msg, dict):
            continue
        title = (
            msg.get("Title") or msg.get("title") or msg.get("name") or ""
        ).strip()
        body = (
            msg.get("MessageText") or msg.get("description")
            or msg.get("body") or msg.get("message") or ""
        )
        if isinstance(body, dict):
            body = body.get("content") or body.get("text") or str(body)
        body = str(body).strip()[:800]
        url = msg.get("ExternalLink") or msg.get("link") or msg.get("url") or source["url"]
        date = (
            msg.get("LastModifiedTime") or msg.get("StartTime")
            or msg.get("published") or datetime.now(timezone.utc).isoformat()
        )
        if not title:
            continue
        items.append({
            "source": source["name"],
            "title": title,
            "body": body,
            "url": url,
            "date": date,
        })
    log.info(f"    → {len(items)} items from JSON API")
    return items


def fetch_html(source: dict) -> list[dict]:
    """Fetch items from an HTML page by scraping heading + paragraph pairs."""
    log.info(f"  HTML → {source['name']}")
    try:
        resp = SESSION.get(source["url"], timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning(f"    Failed to fetch {source['name']}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items = []
    article = soup.find("main") or soup.find("article") or soup.body

    if not article:
        return []

    # Exact-match boilerplate headings to skip
    NOISE_TITLES = {
        "in this article", "feedback", "additional resources", "next steps",
        "prerequisites", "see also", "related articles", "overview",
        "current version", "tip", "note", "important", "warning",
        "known issues",       # page-level section header (e.g. top of Autopilot page)
        "known issue",
    }
    # Prefix-match for longer/variant boilerplate phrases
    NOISE_PREFIXES = (
        "questions",           # "Questions? Join office hours!", "Questions?" etc.
        "submit feedback",     # "Submit feedback"
        "submit and view",     # "Submit and view feedback"
        "view all page",       # "View all page feedback"
        "was this page",       # "Was this page helpful?"
        "need help",           # "Need help?"
        "additional versions", # Windows Release Health section footer
        "review your",         # "Review your settings" — guidance, not a known issue
        "implement required",  # "Implement required Enterprise Application permissions"
        "join office hours",   # "Join office hours!"
    )

    # Walk h2/h3 headings — each becomes a potential item
    headings = article.find_all(["h2", "h3"])
    for heading in headings[:25]:
        title = heading.get_text(strip=True)
        if len(title) < 10:
            continue
        title_lower = title.lower()
        if title_lower in NOISE_TITLES:
            continue
        if any(title_lower.startswith(p) for p in NOISE_PREFIXES):
            continue
        # Skip "Week of ..." date headings — they're section separators, not items
        if title_lower.startswith("week of ") or title_lower.startswith("month of "):
            continue
        # Collect following paragraphs until next heading
        body_parts = []
        for sib in heading.find_next_siblings():
            if sib.name in ["h2", "h3"]:
                break
            if sib.name in ["p", "li"]:
                body_parts.append(sib.get_text(strip=True))
            if len(body_parts) >= 4:
                break
        body = " ".join(body_parts)[:800]

        # Some sources (e.g. Defender Antivirus error-code pages) use a bare event
        # ID or numeric code as the heading. If the source defines title_from_body,
        # scan the body parts for that label and promote its value to the display title.
        display_title = title
        title_from_body = source.get("title_from_body")
        if title_from_body:
            for part in body_parts:
                if part.lower().startswith(title_from_body.lower()):
                    extracted = part[len(title_from_body):].lstrip(": ").strip()
                    if extracted:
                        display_title = f"{title} — {extracted}"
                    break

        # Use the heading's id attribute (if present) to build a direct anchor URL.
        # Microsoft Learn pages always set id on headings matching the URL slug,
        # so this produces links like /autopilot/known-issues#issue-heading-slug.
        heading_id = heading.get("id", "")
        item_url = f"{source['url']}#{heading_id}" if heading_id else source["url"]
        items.append({
            "source": source["name"],
            "title": display_title,
            "body": body,
            "url": item_url,
            "date": datetime.now(timezone.utc).date().isoformat(),
        })
    return items


def enrich_item(raw: dict) -> dict:
    """Add classification, phase, action fields to a raw item."""
    category, matched = classify_item(raw["title"], raw["body"])
    # Microsoft Viva's "Research Drop" posts are WorkLab-style workplace/AI
    # research essays, not product feature updates. Keyword-classifying them
    # into the six pillars was why they never surfaced: they don't carry
    # admin actions or engineer-relevant substance, so they lost out to
    # Teams/Copilot/Defender volume in whichever pillar they landed in.
    # Routing them to their own bucket lets digest.py give them dedicated,
    # exec-only treatment instead of silently dropping them. This is an
    # intentional override, not a fallback, so matched stays True.
    if raw["source"] == "Microsoft Viva" and raw["title"].startswith("Research Drop"):
        category = "Research & Trends"
        matched = True
    phase = detect_phase(raw["title"], raw["body"])
    action = detect_admin_action(raw["body"])
    iid = item_id(raw["source"], raw["title"])
    return {
        "id": iid,
        "source": raw["source"],
        "title": raw["title"],
        "body": raw["body"][:600],
        "url": raw["url"],
        "date": raw["date"],
        "category": category,
        "category_matched": matched,
        "phase": phase,
        "admin_action": action,
        "impacted_workloads": [raw["source"]],
        "is_updated": False,
    }


def load_health_baseline() -> set:
    """Load the set of issue titles recorded at the last digest publish.

    Returns an empty set if no baseline exists yet (first run).
    """
    if not HEALTH_BASELINE_FILE.exists():
        return set()
    try:
        with open(HEALTH_BASELINE_FILE) as f:
            data = json.load(f)
        return set(data.get("titles", []))
    except Exception as e:
        log.warning(f"Could not read health baseline: {e}")
        return set()


def write_health_data(health_items: list[dict]):
    """Write health/known-issues items to site/data/health.json for Hugo.

    Groups items by source. Each item is tagged is_new=True when its title
    was not present in the last-published baseline (health_baseline.json).
    The sidebar uses this to show only net-new issues since the last digest.
    """
    baseline = load_health_baseline()

    # Group items by source
    grouped = {}
    for item in health_items:
        src = item["source"]
        if src not in grouped:
            grouped[src] = {"name": src, "url": item["url"], "count": 0, "new_count": 0, "items": []}
        is_new = item["title"] not in baseline
        grouped[src]["count"] += 1
        if is_new:
            grouped[src]["new_count"] += 1
        grouped[src]["items"].append({
            "title": item["title"],
            "body": item["body"][:300],
            "url": item["url"],
            "is_new": is_new,
        })

    total_new = sum(g["new_count"] for g in grouped.values())
    payload = {
        "updated": datetime.now(timezone.utc).date().isoformat(),
        "status_url": "https://status.cloud.microsoft",
        "total_count": len(health_items),
        "total_new_count": total_new,
        "sources": list(grouped.values()),
    }
    with open(HEALTH_DATA_FILE, "w") as f:
        json.dump(payload, f, indent=2)
    log.info(f"Health data written → {HEALTH_DATA_FILE} ({len(health_items)} items, {total_new} new since last digest)")


CLASSIFICATION_STATS_FILE = STATE_DIR / "classification_stats.json"
CLASSIFICATION_STATS_HISTORY_LIMIT = 52  # roughly a year of weekly runs


def write_classification_stats(new_items: list[dict], grouped: dict, run_date: str):
    """Append this run's classification breakdown to a rolling stats file.

    Tracks per-category item counts and how many items fell back to
    DEFAULT_CATEGORY (category_matched=False) instead of a real keyword hit.
    A rising fallback rate, or a pillar that stays empty run after run, is
    the signal that the keyword lists in sources.py need new terms — visible
    here instead of requiring manual inspection of pending_draft.json, which
    is how the Viva/Roadmap issues were originally found.
    """
    history = []
    if CLASSIFICATION_STATS_FILE.exists():
        try:
            with open(CLASSIFICATION_STATS_FILE) as f:
                history = json.load(f).get("history", [])
        except Exception as e:
            log.warning(f"Could not read {CLASSIFICATION_STATS_FILE}, starting fresh: {e}")

    fallback_items = [it for it in new_items if not it.get("category_matched", True)]
    entry = {
        "run_date": run_date,
        "total_items": len(new_items),
        "by_category": {cat: len(items) for cat, items in grouped.items()},
        "fallback_count": len(fallback_items),
        "fallback_titles": [it["title"] for it in fallback_items][:10],
    }
    history.append(entry)
    history = history[-CLASSIFICATION_STATS_HISTORY_LIMIT:]

    with open(CLASSIFICATION_STATS_FILE, "w") as f:
        json.dump({"history": history}, f, indent=2)
    log.info(
        f"Classification stats recorded — {entry['total_items']} items, "
        f"{entry['fallback_count']} fallback → {CLASSIFICATION_STATS_FILE}"
    )


def purge_expired_deadlines():
    """Remove past deadlines from deadlines.json and refresh the updated date.

    Called from run_health_only() so it runs automatically every 8 hours —
    keeping the 'Last checked' date current and trimming expired entries.
    """
    deadline_file = BASE_DIR / "site" / "data" / "deadlines.json"
    if not deadline_file.exists():
        log.info("deadlines.json not found — skipping deadline purge.")
        return
    try:
        with open(deadline_file) as f:
            data = json.load(f)
        today = datetime.now(timezone.utc).date().isoformat()
        before = len(data.get("deadlines", []))
        data["deadlines"] = [
            d for d in data.get("deadlines", [])
            if d.get("date", "9999-99-99") >= today
        ]
        after = len(data["deadlines"])
        data["updated"] = today
        with open(deadline_file, "w") as f:
            json.dump(data, f, indent=2)
        removed = before - after
        log.info(f"Deadlines refreshed — {removed} expired removed, {after} remaining, updated → {today}")
    except Exception as e:
        log.warning(f"Failed to refresh deadlines.json (non-fatal): {e}")


def run_health_only():
    """Scrape only health/known-issues sources and update health.json.

    Intentionally lightweight — no dedup, no draft, no state changes.
    Called by the every-8-hours health cron job.
    """
    log.info("Health-only mode — scraping known issues sources.")
    health_sources = [s for s in SOURCES if s.get("health")]
    if not health_sources:
        log.warning("No health sources defined in sources.py.")
        return

    health_raw = []
    for source in health_sources:
        log.info(f"Fetching: {source['name']}")
        try:
            if source.get("json_api"):
                raw_items = fetch_json_status(source)
            elif source.get("rss"):
                raw_items = fetch_rss(source)
            else:
                raw_items = fetch_html(source)
        except Exception as e:
            log.warning(f"  Error on {source['name']}: {e}")
            raw_items = []
        log.info(f"  → {len(raw_items)} items")
        health_raw.extend(raw_items)
        time.sleep(REQUEST_DELAY)

    if health_raw:
        health_items = [enrich_item(r) for r in health_raw]
        write_health_data(health_items)
    else:
        log.warning("Health sources returned 0 items — health.json not updated.")

    purge_expired_deadlines()
    log.info("Health-only run complete.")


def run_scraper(args):
    if args.health_only:
        run_health_only()
        return

    state = load_state()
    seen_ids = set(state.get("seen_ids", []))
    log.info(f"State loaded — {len(seen_ids)} previously seen items.")

    # Filter sources if --source flag used
    sources_to_run = SOURCES
    if args.source:
        sources_to_run = [s for s in SOURCES if args.source.lower() in s["name"].lower()]
        if not sources_to_run:
            log.error(f"No source matching '{args.source}'. Check sources.py.")
            sys.exit(1)

    all_raw = []
    health_raw = []
    for source in sources_to_run:
        log.info(f"Fetching: {source['name']}")
        try:
            if source.get("json_api"):
                raw_items = fetch_json_status(source)
            elif source.get("rss"):
                raw_items = fetch_rss(source)
            else:
                raw_items = fetch_html(source)
        except Exception as e:
            log.warning(f"  Error on {source['name']}: {e}")
            raw_items = []

        log.info(f"  → {len(raw_items)} raw items fetched.")
        if source.get("health"):
            health_raw.extend(raw_items)
        else:
            all_raw.extend(raw_items)
        time.sleep(REQUEST_DELAY)

    # Write health items to site/data/health.json (always overwrite — no dedup needed)
    if health_raw:
        health_items = [enrich_item(r) for r in health_raw]
        write_health_data(health_items)
    elif any(s.get("health") for s in sources_to_run):
        log.warning("Health sources returned 0 items — health.json not updated.")

    # Always refresh the deadlines.json updated timestamp (and purge expired entries)
    # so the site's "Last checked" date stays current on every run, not just health-only runs.
    purge_expired_deadlines()

    # URL dedup — shared RSS feeds (e.g. MicrosoftSecurityBlog used by 4 Defender sources)
    # can return the same article multiple times under different source names.
    # Keep the first occurrence; subsequent duplicates are logged and dropped.
    seen_urls: set = set()
    deduped_raw = []
    for item in all_raw:
        url = item.get("url", "")
        if url and url in seen_urls:
            log.debug(f"  URL dedup: dropped '{item['title']}' from {item['source']} (already seen)")
            continue
        if url:
            seen_urls.add(url)
        deduped_raw.append(item)
    if len(deduped_raw) < len(all_raw):
        log.info(f"URL dedup removed {len(all_raw) - len(deduped_raw)} cross-source duplicate(s).")
    all_raw = deduped_raw

    # Enrich and dedup digest items against seen_ids, with a published-post
    # backstop (see load_published_urls) in case seen_items.json missed it.
    published_urls = load_published_urls(POSTS_DIR)
    log.info(f"Backstop dedup — {len(published_urls)} URLs already published in category sections.")

    new_items = []
    backstop_dropped = 0
    for raw in all_raw:
        enriched = enrich_item(raw)
        if not args.force_all and enriched["id"] in seen_ids:
            continue  # already seen, skip
        bare_url = enriched["url"].split("#")[0]
        if bare_url in published_urls:
            backstop_dropped += 1
            log.info(f"  Backstop dedup: '{enriched['title']}' already published — seen_items.json missed it, skipping.")
            seen_ids.add(enriched["id"])  # repair state while we're here
            continue
        new_items.append(enriched)

    log.info(f"New items after dedup: {len(new_items)}")
    if backstop_dropped:
        log.info(f"Backstop dedup caught {backstop_dropped} item(s) that seen_items.json missed.")

    # Age backstop — a title/source hash that's never been seen before isn't
    # necessarily new content. Low-volume feeds can return entries months
    # old the first time they're scraped (or right after a source is added
    # to sources.py). Drop those here instead of letting them accumulate in
    # pending_draft.json; still mark them seen so they aren't re-evaluated
    # every run.
    stale_dropped = 0
    age_filtered = []
    for item in new_items:
        age = item_age_days(item.get("date"))
        if age is not None and age > MAX_PENDING_AGE_DAYS:
            log.info(f"  Age backstop: dropping '{item['title'][:60]}' from {item['source']} — {age:.0f} days old.")
            seen_ids.add(item["id"])
            stale_dropped += 1
            continue
        age_filtered.append(item)
    new_items = age_filtered
    if stale_dropped:
        log.info(f"Age backstop dropped {stale_dropped} item(s) older than {MAX_PENDING_AGE_DAYS} days.")

    if not new_items:
        log.info("No new items this cycle. Nothing to draft.")
        return

    # Group by category for the draft
    grouped = {}
    for item in new_items:
        cat = item["category"]
        grouped.setdefault(cat, []).append(item)

    run_date = datetime.now(timezone.utc).date().isoformat()
    sources_this_run = [s["name"] for s in sources_to_run]

    write_classification_stats(new_items, grouped, run_date)

    # ── Per-run snapshot (dated, for reference / manual replay) ───────────────
    snapshot = {
        "run_date": run_date,
        "week_of": run_date,
        "total_new_items": len(new_items),
        "sources_checked": sources_this_run,
        "grouped_items": grouped,
        "claude_prompt_hint": (
            "Paste this JSON into Claude.ai with your master prompt. "
            "Ask Claude to produce the weekly digest in the standard format: "
            "Top 5, section highlights, recommended actions, Graph/API hooks, hashtags."
        ),
    }
    draft_path = STATE_DIR / f"weekly_draft_{run_date}.json"
    with open(draft_path, "w") as f:
        json.dump(snapshot, f, indent=2)
    log.info(f"Run snapshot saved → {draft_path}")

    # ── Rolling pending draft (accumulates across runs until digest publishes) ─
    if PENDING_DRAFT_FILE.exists():
        with open(PENDING_DRAFT_FILE) as f:
            pending = json.load(f)

        # Prune items that have aged out since they were added. The pending
        # draft accumulates across however many scraper runs happen before
        # the next digest publishes, so an item added when it was fresh can
        # still be sitting here weeks later if publishing is delayed.
        pruned = 0
        for cat in list(pending.get("grouped_items", {}).keys()):
            kept = []
            for item in pending["grouped_items"][cat]:
                age = item_age_days(item.get("date"))
                if age is not None and age > MAX_PENDING_AGE_DAYS:
                    log.info(f"  Pruned stale pending item ({age:.0f}d): '{item['title'][:60]}' from {item['source']}")
                    pruned += 1
                    continue
                kept.append(item)
            pending["grouped_items"][cat] = kept
        if pruned:
            log.info(f"Pruned {pruned} item(s) from pending draft that aged out (>{MAX_PENDING_AGE_DAYS}d).")

        # Collect IDs already in the pending draft to avoid double-adding
        existing_ids = {
            item["id"]
            for cat_items in pending.get("grouped_items", {}).values()
            for item in cat_items
        }
        added = 0
        for item in new_items:
            if item["id"] not in existing_ids:
                cat = item["category"]
                pending["grouped_items"].setdefault(cat, []).append(item)
                existing_ids.add(item["id"])
                added += 1
        pending["last_updated"] = run_date
        pending["runs"] = pending.get("runs", []) + [run_date]
        pending["total_new_items"] = sum(
            len(v) for v in pending["grouped_items"].values()
        )
        # Union of all sources checked across runs
        pending["sources_checked"] = list(
            set(pending.get("sources_checked", [])) | set(sources_this_run)
        )
        log.info(
            f"Pending draft updated — {added} new items added, "
            f"{pending['total_new_items']} total accumulated."
        )
    else:
        # First run since last digest — start a fresh pending draft
        pending = {
            "week_of": run_date,       # overwritten by digest.py to the publish date
            "last_updated": run_date,
            "runs": [run_date],
            "total_new_items": len(new_items),
            "sources_checked": sources_this_run,
            "grouped_items": grouped,
        }
        log.info(f"Pending draft created — {len(new_items)} items.")

    with open(PENDING_DRAFT_FILE, "w") as f:
        json.dump(pending, f, indent=2)
    log.info(f"Pending draft saved → {PENDING_DRAFT_FILE}")

    # Update state
    for item in new_items:
        seen_ids.add(item["id"])
    state["seen_ids"] = list(seen_ids)
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    state["total_items_seen"] = len(seen_ids)
    save_state(state)

    print(f"\n{'='*60}")
    print(f"  Run snapshot:    {draft_path}")
    print(f"  New this run:    {len(new_items)}")
    print(f"  Pending total:   {pending['total_new_items']} items across {len(pending['runs'])} run(s)")
    print(f"  Next step:       python digest.py  (reads pending_draft.json)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Modern Work Weekly scraper")
    parser.add_argument("--force-all", action="store_true",
                        help="Ignore seen_items state and pull all available items")
    parser.add_argument("--source", type=str, default=None,
                        help="Only scrape a specific source by name (e.g. 'Intune')")
    parser.add_argument("--health-only", action="store_true",
                        help="Scrape only health/known-issues sources and update health.json (no draft changes)")
    args = parser.parse_args()
    run_scraper(args)
