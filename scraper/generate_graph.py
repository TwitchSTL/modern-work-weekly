#!/usr/bin/env python3
"""
generate_graph.py — Regenerate the Tag Universe's data block in
site/static/universe/index.html from the real published posts.

Mirrors generate_search_index.py's approach (regex front-matter parsing,
no PyYAML dependency, matches scraper/requirements.txt) but targets the
Tag Universe globe's WEEKS / TAG_SEED / DOCS_NODES / EDGES constants
instead of search.json.

Why this exists: as of 2026-08-18, universe/index.html's tag data was a
one-time hand-extraction ("REAL DATA — extracted 2026-08-15 from this
repo's 16 published posts") with no automated refresh — every week the
digest runs, the globe drifts one week further out of date. This script
closes that gap and is meant to run from weekly-run.sh right after
digest.py, the same way generate_search_index.py already does.

Reproduces the same tag -> pillar map used by
site/layouts/partials/topics-sidebar.html and terms.html (kept in sync
manually across all three — see this file's PILLAR_TAG_MAP comment) and
the same EDGES pruning approach documented inline in universe/index.html's
"Round 13" comment: rank each tag's co-occurring partners by Jaccard
similarity (shared weeks / union of weeks either tag appeared in) rather
than raw shared-week count, so high-frequency "hub" tags like copilot/
zero-trust don't crowd out every other tag's real strongest relationship.
Keep the top 2 partners per tag, subject to a raw floor of >= 3 shared
weeks, then dedupe into one undirected edge list.

Usage:
    python generate_graph.py            # Regenerate and write index.html
    python generate_graph.py --dry-run  # Print the generated block only
"""

import argparse
import itertools
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
POSTS_DIR = BASE_DIR / "site" / "content" / "posts"
UNIVERSE_PATH = BASE_DIR / "site" / "static" / "universe" / "index.html"

RE_FRONTMATTER_SEP = re.compile(r'^---\s*$')

# Same hand-maintained tag -> pillar map as topics-sidebar.html / terms.html.
# Kept in sync manually across all three for the same reason documented in
# topics-sidebar.html: not computed dynamically from Hugo taxonomy relations.
PILLAR_TAG_MAP = {
    "entra-id": "Identity & Access",
    "identity": "Identity & Access",
    "conditional-access": "Identity & Access",
    "global-secure-access": "Identity & Access",
    "intune": "Endpoint & Device Management",
    "endpoint-management": "Endpoint & Device Management",
    "windows": "Endpoint & Device Management",
    "windows-365": "Endpoint & Device Management",
    "windows-autopatch": "Endpoint & Device Management",
    "autopilot": "Endpoint & Device Management",
    "hotpatch": "Endpoint & Device Management",
    "linux": "Endpoint & Device Management",
    "teams-rooms": "Endpoint & Device Management",
    "exchange": "Collaboration & Productivity",
    "teams": "Collaboration & Productivity",
    "sharepoint": "Collaboration & Productivity",
    "onedrive": "Collaboration & Productivity",
    "copilot": "AI & Copilot",
    "copilot-studio": "AI & Copilot",
    "power-platform": "AI & Copilot",
    "shadow-ai": "AI & Copilot",
    "agent-365": "AI & Copilot",
    "viva": "Employee Experience",
    "zero-trust": "Security & Compliance",
    "defender-xdr": "Security & Compliance",
    "defender-for-endpoint": "Security & Compliance",
    "defender-for-identity": "Security & Compliance",
    "defender-for-office-365": "Security & Compliance",
    "purview": "Security & Compliance",
    "data-lifecycle": "Security & Compliance",
    "dspm": "Security & Compliance",
    "security": "Security & Compliance",
}

# Branding tag on every post — not a content signal. Excluded from TAG_SEED
# the same way topics-sidebar.html's comment describes.
EXCLUDED_TAGS = {"modern-work"}

PILLAR_ORDER = [
    "Identity & Access",
    "Endpoint & Device Management",
    "Collaboration & Productivity",
    "AI & Copilot",
    "Employee Experience",
    "Security & Compliance",
]

JACCARD_TOP_N = 2
RAW_WEIGHT_FLOOR = 3

START_MARKER = "  // GENERATED:GRAPH:START - do not hand-edit below this line, run scraper/generate_graph.py instead"
END_MARKER = "  // GENERATED:GRAPH:END"


def parse_frontmatter(lines):
    """Parse YAML-ish front matter; returns (fields dict, body_lines)."""
    fields = {}
    if not lines or not RE_FRONTMATTER_SEP.match(lines[0]):
        return fields, lines

    i = 1
    in_list_key = None
    while i < len(lines):
        line = lines[i]
        if RE_FRONTMATTER_SEP.match(line):
            return fields, lines[i + 1:]
        if in_list_key and line.startswith('  - '):
            val = line.strip().lstrip('- ').strip().strip('"').strip("'")
            fields[in_list_key].append(val)
            i += 1
            continue
        in_list_key = None
        if ':' in line:
            key, _, val = line.partition(':')
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if val == '':
                fields[key] = []
                in_list_key = key
            else:
                fields[key] = val
        i += 1
    return fields, lines[i:]


def load_posts():
    """Return list of (date_str, tags, body_lines) for every real published
    post, sorted by date. Skips .bak files and anything whose front matter
    doesn't parse to a date — same defensive posture as generate_search_index.py."""
    posts = []
    for path in sorted(POSTS_DIR.glob("*.md")):
        if path.name.endswith(".bak"):
            continue
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        fields, body = parse_frontmatter(lines)
        date = fields.get("date", "").strip()
        if not date:
            continue
        tags = [t for t in fields.get("tags", []) if t not in EXCLUDED_TAGS]
        posts.append((date, tags, body))
    posts.sort(key=lambda p: p[0])
    return posts


def build_weeks_and_tags(posts):
    weeks = [d for d, _, _ in posts]
    tag_weeks = {}
    for i, (_, tags, _) in enumerate(posts):
        for tag in tags:
            presence = tag_weeks.setdefault(tag, [0] * len(weeks))
            presence[i] = 1
    return weeks, tag_weeks


def parse_docs_updates(body_lines):
    """Return {pillar: count} of bullet items under each '**Pillar**'
    sub-header inside a '## Documentation Updates' section."""
    counts = {}
    in_docs = False
    current_pillar = None
    for line in body_lines:
        if line.startswith("## "):
            in_docs = line.strip() == "## Documentation Updates"
            current_pillar = None
            continue
        if not in_docs:
            continue
        stripped = line.strip()
        m = re.match(r'^\*\*(.+?)\*\*$', stripped)
        if m:
            current_pillar = m.group(1).strip()
            continue
        if current_pillar and re.match(r'^[-*]\s+', stripped):
            counts[current_pillar] = counts.get(current_pillar, 0) + 1
    return counts


def build_docs_nodes(posts, weeks):
    # pillar -> {week: count}
    real = {p: {} for p in PILLAR_ORDER}
    for date, _, body in posts:
        counts = parse_docs_updates(body)
        for pillar, n in counts.items():
            if pillar in real:
                real[pillar][date] = n
    return real


def jaccard_edges(weeks, tag_weeks):
    """Top-JACCARD_TOP_N partners per tag by Jaccard similarity, floored by
    raw shared-week count >= RAW_WEIGHT_FLOOR, deduped into one undirected list."""
    tags = sorted(tag_weeks.keys())
    shared = {}
    union = {}
    for a, b in itertools.combinations(tags, 2):
        pa, pb = tag_weeks[a], tag_weeks[b]
        s = sum(1 for x, y in zip(pa, pb) if x and y)
        u = sum(1 for x, y in zip(pa, pb) if x or y)
        if s >= RAW_WEIGHT_FLOOR:
            shared[(a, b)] = s
            union[(a, b)] = u

    def jaccard(a, b):
        key = (a, b) if (a, b) in shared else (b, a)
        if key not in shared or union[key] == 0:
            return 0.0
        return shared[key] / union[key]

    partners = {t: [] for t in tags}
    for (a, b) in shared:
        partners[a].append(b)
        partners[b].append(a)

    edges = set()
    for tag in tags:
        ranked = sorted(partners[tag], key=lambda other: jaccard(tag, other), reverse=True)
        for other in ranked[:JACCARD_TOP_N]:
            key = tuple(sorted((tag, other)))
            edges.add(key)

    result = []
    for a, b in edges:
        key = (a, b) if (a, b) in shared else (b, a)
        result.append((a, b, shared[key]))
    result.sort(key=lambda e: -e[2])
    return result


def js_str_list(items):
    return "[" + ",".join(f'"{i}"' for i in items) + "]"


def render_block(weeks, tag_weeks, docs_real, edges):
    lines = [START_MARKER]
    lines.append(f"  const WEEKS = {js_str_list(weeks)};")
    lines.append("")
    lines.append("  const TAG_SEED = [")
    # Order tags by total presence descending, then name, for stable/readable diffs.
    ordered = sorted(
        tag_weeks.items(),
        key=lambda kv: (-sum(kv[1]), kv[0]),
    )
    for tag, presence in ordered:
        pillar = PILLAR_TAG_MAP.get(tag)
        if not pillar:
            # Unmapped tag — skip rather than guess; keeps the globe honest
            # about what it actually knows the pillar of. Add the tag to
            # PILLAR_TAG_MAP above once its pillar is confirmed.
            continue
        arr = "[" + ",".join(str(v) for v in presence) + "]"
        lines.append(f'    ["{tag}", "{pillar}", {arr}],')
    lines.append("  ];")
    lines.append("")
    lines.append("  const NODES = TAG_SEED.map(([tag, pillar, presence]) => {")
    lines.append("    const weekly = presence.map((count, i) => ({ week: WEEKS[i], count }));")
    lines.append("    return { tag, pillar, total: presence.reduce((a, c) => a + c, 0), weekly };")
    lines.append("  });")
    lines.append("")
    lines.append("  const DOCS_REAL = {")
    for pillar in PILLAR_ORDER:
        table = docs_real.get(pillar, {})
        entries = ",".join(f'"{wk}":{n}' for wk, n in table.items())
        lines.append(f'    "{pillar}": {{{entries}}},')
    lines.append("  };")
    lines.append("  const DOCS_NODES = PILLARS.map(p => {")
    lines.append("    const table = DOCS_REAL[p.name] || {};")
    lines.append("    const weekly = WEEKS.map(week => ({ week, count: table[week] || 0 }));")
    lines.append("    return { pillar: p.name, total: weekly.reduce((a, w) => a + w.count, 0), weekly };")
    lines.append("  });")
    lines.append("")
    lines.append("  const EDGES = [")
    for a, b, w in edges:
        lines.append(f'    ["{a}", "{b}", {w}],')
    lines.append("  ];")
    lines.append(END_MARKER)
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Regenerate Tag Universe data in universe/index.html")
    parser.add_argument("--dry-run", action="store_true", help="Print the generated block only")
    args = parser.parse_args()

    posts = load_posts()
    if not posts:
        print("No posts found — aborting, refusing to write an empty graph.", file=sys.stderr)
        sys.exit(1)

    weeks, tag_weeks = build_weeks_and_tags(posts)
    docs_real = build_docs_nodes(posts, weeks)
    edges = jaccard_edges(weeks, tag_weeks)
    block = render_block(weeks, tag_weeks, docs_real, edges)

    if args.dry_run:
        print(block)
        return

    html = UNIVERSE_PATH.read_text(encoding="utf-8")
    if START_MARKER not in html or END_MARKER not in html:
        print(
            f"ERROR: {UNIVERSE_PATH} is missing the GENERATED:GRAPH markers. "
            "Run with --dry-run and paste the block in manually once, wrapped "
            "in the markers shown at the top of this script, then re-run.",
            file=sys.stderr,
        )
        sys.exit(1)

    pre, rest = html.split(START_MARKER, 1)
    _, post = rest.split(END_MARKER, 1)
    new_html = pre + block.rstrip("\n") + post
    UNIVERSE_PATH.write_text(new_html, encoding="utf-8")
    print(f"Wrote {len(weeks)} weeks, {len(tag_weeks)} tags, {len(edges)} edges to {UNIVERSE_PATH}")


if __name__ == "__main__":
    main()
