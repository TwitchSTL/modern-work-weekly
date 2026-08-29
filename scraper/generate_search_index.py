#!/usr/bin/env python3
"""
generate_search_index.py — Build site/static/search.json from all digest posts.

Reads every markdown file in site/content/posts/, extracts per-article entries
(title, category, snippet, url, date) using the same state machine logic as the
Hugo template that failed to generate the output format reliably.

Writing to site/static/ means Hugo serves the file directly at /search.json
with zero template involvement — no output format quirks, no version issues.

Usage:
    python generate_search_index.py           # Regenerate and write search.json
    python generate_search_index.py --dry-run # Print JSON to stdout only
"""

import argparse
import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
POSTS_DIR = BASE_DIR / "site" / "content" / "posts"
OUTPUT_PATH = BASE_DIR / "site" / "static" / "search.json"

# Regexes matching digest markdown formats
RE_FRONTMATTER_SEP = re.compile(r'^---\s*$')
RE_H2 = re.compile(r'^## (.+)')
RE_H3 = re.compile(r'^### (.+)')
RE_BULLET_TITLE = re.compile(r'^\s*[-*\d]+\.?\s+\*\*(.+?)\*\*')
RE_PHASE_TAG = re.compile(r'^`[^`]+`\s*[—–-]?\s*')
RE_STRIP_INLINE = re.compile(r'\*{1,3}[^*]+\*{1,3}|\`[^`]+\`')  # strip bold/italic/code
# Added 2026-08-29 alongside the emphasis-tag feature: extracts the
# optional {{< emphasis "..." >}} shortcode from an item's line so it can
# be captured into search.json as its own field, and strips both this and
# the pre-existing {{< cat "..." >}} shortcode out of snippet text — found
# during this same change that {{< cat >}} was leaking into Top 5 item
# snippets verbatim (never stripped here, only ever consumed by
# collapsible.js client-side), so both shortcodes get the same treatment
# now rather than leaving the emphasis one to repeat that same bug.
RE_EMPHASIS_TAG = re.compile(r'\{\{<\s*emphasis\s+"([^"]*)"\s*>\}\}')
RE_ANY_SHORTCODE = re.compile(r'\{\{<[^>]*>\}\}')


def strip_markdown_inline(text: str) -> str:
    """Remove common inline markdown so snippets read as plain text."""
    text = RE_ANY_SHORTCODE.sub('', text)                    # {{< ... >}} shortcodes
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)   # bold/italic
    text = re.sub(r'`([^`]+)`', r'\1', text)                 # inline code
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)     # links
    return text.strip()


def parse_frontmatter(lines: list[str]) -> tuple[dict, int]:
    """Parse YAML-ish front matter; returns (fields dict, body_start_index)."""
    fields: dict = {}
    if not lines or not RE_FRONTMATTER_SEP.match(lines[0]):
        return fields, 0

    i = 1
    in_list_key = None
    while i < len(lines):
        line = lines[i]
        if RE_FRONTMATTER_SEP.match(line):
            return fields, i + 1
        # List continuation
        if in_list_key and line.startswith('  - '):
            val = line.strip().lstrip('- ').strip().strip('"').strip("'")
            fields[in_list_key].append(val)
            i += 1
            continue
        in_list_key = None
        # Key: value
        if ':' in line:
            key, _, val = line.partition(':')
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if val == '':
                # might be a list
                fields[key] = []
                in_list_key = key
            elif val.startswith('['):
                # inline list: ["a", "b"]
                items = re.findall(r'"([^"]+)"|\'([^\']+)\'|(\w[\w &]+)', val)
                fields[key] = [a or b or c for a, b, c in items if (a or b or c)]
            else:
                fields[key] = val
        i += 1
    return fields, i


def derive_url(post_path: Path) -> str:
    """Produce the Hugo permalink for a post file (e.g. /posts/2026-05-17/)."""
    stem = post_path.stem  # e.g. "2026-05-17"
    return f"/posts/{stem}/"


def extract_entries(post_path: Path) -> list[dict]:
    """Parse one post file and return a list of per-article search entries."""
    raw = post_path.read_text(encoding="utf-8")
    lines = raw.splitlines()

    fm, body_start = parse_frontmatter(lines)

    # Skip posts with no categories (e.g. the intro/welcome post)
    categories = fm.get("categories", [])
    if not categories:
        return []

    date = fm.get("date", "")
    url = derive_url(post_path)

    entries: list[dict] = []
    category = ""
    pending_title = ""
    pending_emphasis: list[str] = []

    def flush_pending(snippet_line: str = ""):
        nonlocal pending_title, pending_emphasis
        if not pending_title:
            return
        snippet = strip_markdown_inline(RE_PHASE_TAG.sub("", snippet_line).strip())
        if not snippet:
            snippet = strip_markdown_inline(snippet_line)
        entry = {
            "title": pending_title,
            "category": category,
            "date": date,
            "url": url,
            "snippet": snippet[:220],
        }
        if pending_emphasis:
            entry["emphasis"] = pending_emphasis
        entries.append(entry)
        pending_title = ""
        pending_emphasis = []

    for raw_line in lines[body_start:]:
        line = raw_line.rstrip("\r")
        trimmed = line.strip()

        # Section heading (h2) — update category, flush any pending title
        m2 = RE_H2.match(trimmed)
        if m2:
            flush_pending()
            category = m2.group(1).strip()
            continue

        # h3 article title (format B)
        m3 = RE_H3.match(trimmed)
        if m3:
            flush_pending()
            # Strip trailing " · *GA*" style phase markers
            title = re.sub(r'\s*[·•]\s*\*[^*]+\*$', '', m3.group(1)).strip()
            title = strip_markdown_inline(title)
            pending_title = title
            continue

        # Bullet with bold title (format A): - **Title** `GA` — description
        mb = RE_BULLET_TITLE.match(line)
        if mb:
            flush_pending()
            raw_title = mb.group(1).strip()
            title = strip_markdown_inline(raw_title)
            pending_title = title

            # Check if description is inline (after the `XX` tag)
            after = line[mb.end():]  # everything after the **Title**
            # Strip closing ** if title was extracted mid-pattern
            after = re.sub(r'^\*\*', '', after)
            # Strip phase tag like `GA` or `Preview`
            after = re.sub(r'^`[^`]+`', '', after).strip()
            # Extract the optional emphasis shortcode (forward-only tag,
            # see the 2026-08-29 emphasis-tag feature) before stripping it
            # like any other shortcode below.
            em_match = RE_EMPHASIS_TAG.search(after)
            if em_match:
                pending_emphasis = [t.strip() for t in em_match.group(1).split(",") if t.strip()]
                after = RE_EMPHASIS_TAG.sub('', after).strip()
            # Strip em-dash separator
            after = re.sub(r'^[—–-]+\s*', '', after).strip()
            if after and len(after) > 10:
                flush_pending(after)
            continue

        # Separator line — drop pending (it had no snippet)
        if trimmed == '---':
            pending_title = ""
            continue

        # Blank line — carry pending forward (description may be on next line)
        if not trimmed:
            continue

        # Continuation line with pending title — this is the snippet
        if pending_title:
            # Skip lines that are clearly not descriptions
            if trimmed.startswith('[') and '](' in trimmed:
                continue  # markdown link line
            if trimmed.startswith('`') and len(trimmed) <= 35:
                continue  # bare phase tag line
            flush_pending(trimmed)

    flush_pending()  # end of file
    return entries


def build_index(posts_dir: Path) -> list[dict]:
    entries: list[dict] = []
    post_files = sorted(posts_dir.glob("*.md"), reverse=True)
    for post_path in post_files:
        try:
            found = extract_entries(post_path)
            entries.extend(found)
            print(f"  {post_path.name}: {len(found)} entries", file=sys.stderr)
        except Exception as exc:
            print(f"  WARNING: skipped {post_path.name}: {exc}", file=sys.stderr)
    return entries


def main():
    parser = argparse.ArgumentParser(description="Generate site/static/search.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print JSON to stdout; do not write file")
    args = parser.parse_args()

    print("Building search index...", file=sys.stderr)
    entries = build_index(POSTS_DIR)
    print(f"Total entries: {len(entries)}", file=sys.stderr)

    payload = json.dumps(entries, ensure_ascii=False, indent=2)

    if args.dry_run:
        print(payload)
    else:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(payload, encoding="utf-8")
        print(f"Written → {OUTPUT_PATH}", file=sys.stderr)
        print(f"Total entries: {len(entries)}", file=sys.stderr)


if __name__ == "__main__":
    main()
