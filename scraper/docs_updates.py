#!/usr/bin/env python3
"""
docs_updates.py — Fetches recent Microsoft documentation commits from GitHub
for the weekly digest's "Documentation Updates" section.

Why this exists: the rest of the pipeline (sources.py) tracks product
"what's new" pages and blogs, which only cover things Microsoft chose to
announce. A retirement notice, a clarified prerequisite, or a quietly
changed default can land as a doc revision with no announcement anywhere
else — this is a blind spot the announcement-based sources structurally
can't catch. Tracking commits to the actual doc source repos catches it.

Repo/path mapping (DOC_SOURCES below) was derived by reading each product's
Learn "what's new" page's own `github_feedback_content_git_url` /
`original_content_git_url` meta tags — the fastest and most reliable way to
find where a product's docs really live. GitHub's repo search and manual
browsing both proved unreliable for this (repo naming has no consistent
pattern, and some products' content lives inside a large shared repo under
a specific subfolder rather than their own repo). See the
project_mww_github_docs_repo_mapping memory for the full research trail,
dead ends, and one real structural gap: Purview has no public GitHub
mirror at all (its Learn page metadata points only to the private
Purview-pr repo), so Security & Compliance doc-tracking only ever covers
Defender.

Noise filtering happens in two layers:
  1. Cheap, deterministic pre-filter here (bot authors, known sync/merge
     message patterns) — kills the bulk of non-substantive commits for
     free before anything reaches Claude.
  2. digest.py's Claude call does the real substance judgment (is this
     commit worth surfacing to an engineer, and if so what's the one or
     two sentence version) — same "code-level enforcement for hard
     rules, LLM judgment for soft calls" split used throughout this
     pipeline.

Requires a GITHUB_TOKEN env var for reliable rate limits: unauthenticated
GitHub API access is capped at 60 requests/hour, which is tight across
~10 source entries plus retries. A token needs no scopes — we only ever
read public repos. Runs without one too, just with less headroom.

Usage (standalone test):
    python docs_updates.py --dry-run          # Print what would be fetched, no filtering detail
    python docs_updates.py                    # Print full JSON to stdout
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

log = logging.getLogger(__name__)

# scraper.py (this module's normal caller) never loads dotenv itself, since
# it historically never needed an API key. Load it here instead, mirroring
# digest.py's ENV_FILE convention, so GITHUB_TOKEN set in
# /opt/modern-work-weekly/.env is actually visible whether this module is
# imported by scraper.py or run standalone.
_ENV_FILE = Path("/opt/modern-work-weekly/.env")
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)
else:
    load_dotenv()

GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# ── Repo/path mapping per Modern Work pillar ────────────────────────────────
# `path: None` means track the whole repo (it's dedicated to one product,
# nothing else lives there). Branch is deliberately NOT specified — the
# commits API defaults to each repo's actual default branch when `sha` is
# omitted, which avoids hardcoding a branch name that could be wrong (some
# of these repos default to "main", others to "public"; letting GitHub
# resolve it removes an entire class of silent-wrong-branch bugs).
# 2026-07-28: windows365, OfficeDocs-SharePoint, OfficeDocs-Exchange,
# OfficeDocs-SkypeForBusiness, and viva were all confirmed DEAD — none of
# these repos exist publicly anymore (verified by browsing
# github.com/orgs/MicrosoftDocs/repositories directly, not just an API
# response, to rule out a rate-limit false negative). Their Learn pages'
# github_feedback_content_git_url metadata still points to these names,
# which is what the original repo mapping trusted — that metadata is
# apparently not a reliable existence check, just a template GitHub's
# publishing pipeline generates without verifying the target still exists.
# Checked whether this content moved into the microsoft-365-docs monorepo
# instead: it didn't, that repo only has two real content folders (copilot/
# and microsoft-365/), neither of which is SharePoint/Exchange/Teams/Viva.
# Net effect: Collaboration & Productivity and Employee Experience have NO
# working Documentation Updates source right now, and Endpoint & Device
# Management lost its Windows 365 source (Intune/Autopilot via memdocs
# still work). Re-research where these products' public doc source repos
# actually live (if anywhere) is a real follow-up, not done here.
DOC_SOURCES = [
    {"pillar": "Identity & Access", "repo": "MicrosoftDocs/entra-docs", "path": None},
    {"pillar": "Endpoint & Device Management", "repo": "MicrosoftDocs/memdocs", "path": "intune"},
    {"pillar": "Endpoint & Device Management", "repo": "MicrosoftDocs/memdocs", "path": "autopilot"},
    {"pillar": "AI & Copilot", "repo": "MicrosoftDocs/microsoft-365-docs", "path": "copilot"},
    {"pillar": "Security & Compliance", "repo": "MicrosoftDocs/defender-docs", "path": None},
]

# ── Noise filtering ──────────────────────────────────────────────────────────
# Observed by hand-reviewing defender-docs' commit history 2026-07-28.
# Anything matching these is an automated sync/editorial-bot commit, not a
# real content change worth surfacing.
NOISE_AUTHOR_LOGINS = {
    "learn-build-service-prod[bot]",
    "msec-docs-bot[bot]",
    "prmerger-automator[bot]",
    "web-flow",  # GitHub's own commit-signing identity for web-based merges
}
NOISE_AUTHOR_NAMES = {
    "learn build service github app",
}
NOISE_MESSAGE_PATTERNS = [
    re.compile(r"^merging changes synced from", re.I),
    re.compile(r"^merge pull request #\d+ from MicrosoftDocs/(main|live)\b", re.I),
    re.compile(r"^resolve syncing conflicts", re.I),
    re.compile(r"^fix\(copy-edit\)", re.I),
    re.compile(r"^\[aira\] bot remediation", re.I),
    re.compile(r"^merge branch '(main|live)' into", re.I),
    re.compile(r"^update \.openpublishing", re.I),
    # Added 2026-07-28 after reviewing the first real dry run against
    # entra-docs and memdocs, which surfaced a lot of purely administrative
    # commits these patterns didn't catch: author/reviewer metadata swaps
    # (no content change at all) and a batch of unlinked "Recover ..."
    # commits from a single author (mmacy-msft) restoring old Intune doc
    # pages with no PR reference, look like pipeline cleanup rather than
    # anything an engineer needs to know changed.
    re.compile(r"^(add|update|change)\s+(author|reviewer)\b", re.I),
    re.compile(r"^change reviewer to author\b", re.I),
    re.compile(r"^update\s+metadata$", re.I),
    re.compile(r"^learn editor:", re.I),
    re.compile(r"^recover\b", re.I),
]


def is_noise_commit(commit: dict) -> bool:
    """True if this commit is bot/sync noise, not a real content change."""
    author_login = ((commit.get("author") or {}).get("login") or "").lower()
    author_name = (commit.get("commit", {}).get("author", {}).get("name") or "").lower()
    if author_login in NOISE_AUTHOR_LOGINS or author_login.endswith("[bot]"):
        return True
    if author_name in NOISE_AUTHOR_NAMES or author_name.endswith("[bot]"):
        return True
    message = commit.get("commit", {}).get("message", "").split("\n")[0].strip()
    for pattern in NOISE_MESSAGE_PATTERNS:
        if pattern.match(message):
            return True
    return False


def _headers() -> dict:
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ModernWorkWeekly/1.0 (docs update tracker; contact via GitHub)",
    }
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def fetch_doc_commits(source: dict, since: datetime) -> list[dict]:
    """Fetch commits for one repo/path since the given datetime, pre-filtered
    for bot/sync noise. Returns raw GitHub commit objects (not yet the
    site's internal item shape — see fetch_all_doc_updates for that).
    """
    repo = source["repo"]
    path = source.get("path")
    label = f"{repo}/{path}" if path else repo
    params = {"since": since.strftime("%Y-%m-%dT%H:%M:%SZ"), "per_page": 100}
    if path:
        params["path"] = path

    try:
        resp = requests.get(
            f"{GITHUB_API}/repos/{repo}/commits",
            headers=_headers(),
            params=params,
            timeout=20,
        )
        resp.raise_for_status()
        commits = resp.json()
    except requests.RequestException as e:
        log.warning(f"  Failed to fetch commits for {label}: {e}")
        return []

    if not isinstance(commits, list):
        log.warning(f"  Unexpected response fetching {label} — expected list, got {type(commits).__name__}")
        return []

    kept = [c for c in commits if not is_noise_commit(c)]
    log.info(f"  {label}: {len(commits)} raw commits, {len(kept)} after noise filter")
    return kept


def fetch_all_doc_updates(days: int = 7) -> dict[str, list[dict]]:
    """Fetch and pre-filter doc commits across every configured source.

    Returns {pillar: [item, ...]} using the same rough item shape as the
    rest of the pipeline (source, title, body, url, date) plus a 'repo'
    field for traceability, so digest.py can treat this consistently
    alongside grouped_items while still telling the two apart.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    results: dict[str, list[dict]] = {}

    for source in DOC_SOURCES:
        commits = fetch_doc_commits(source, since)
        for c in commits:
            message_lines = c.get("commit", {}).get("message", "").split("\n")
            title = message_lines[0].strip()
            author = (
                (c.get("author") or {}).get("login")
                or c.get("commit", {}).get("author", {}).get("name")
                or "unknown"
            )
            sha = c.get("sha", "")
            item = {
                # Full commit SHA as the ID, not a title hash — doc commit
                # messages repeat often ("Update index.md"), so a title-based
                # hash (like scraper.py's item_id()) would silently collide
                # and drop distinct commits. The SHA is unique by construction.
                "id": f"ghc-{sha}",
                "source": f"{source['repo']} docs",
                "title": title,
                "body": f"Doc commit by {author}. File path scope: {source.get('path') or '(whole repo)'}.",
                "url": c.get("html_url", ""),
                "date": c.get("commit", {}).get("author", {}).get("date", ""),
                "repo": source["repo"],
            }
            results.setdefault(source["pillar"], []).append(item)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Fetch recent Microsoft doc commits for Documentation Updates")
    parser.add_argument("--days", type=int, default=7, help="Trailing window in days (default 7)")
    args = parser.parse_args()

    data = fetch_all_doc_updates(days=args.days)
    total = sum(len(v) for v in data.values())
    log.info(f"Total substantive doc commits after filtering: {total}")
    json.dump(data, sys.stdout, indent=2)
    print()
