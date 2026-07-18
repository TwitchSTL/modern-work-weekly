#!/usr/bin/env python3
"""
formatter.py — Converts a Hugo digest Markdown file into a LinkedIn-ready paste.

LinkedIn strips most HTML and Markdown formatting. This script produces
plain text with LinkedIn-friendly structure: line breaks, emoji section
markers, and a clean hashtag block at the end.

Usage:
    python formatter.py ../site/content/posts/2026-05-17.md
    python formatter.py ../site/content/posts/2026-05-17.md --output li_paste.txt
"""

import argparse
import re
import sys
from pathlib import Path


EMOJI_MAP = {
    "Endpoint Management": "🖥️",
    "Identity & Access": "🔐",
    "Security & Compliance": "🛡️",
    "Collaboration & Productivity": "💬",
    "AI & Automation": "🤖",
    "Recommended Actions": "✅",
    "Graph / API": "⚙️",
    "Top 5": "🏆",
}

LINKEDIN_HEADER = """\
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Modern Work Weekly
by First Last
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


def strip_frontmatter(text: str) -> tuple[dict, str]:
    """Extract Hugo front matter and return (meta dict, body text)."""
    meta = {}
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip().strip('"')
            return meta, parts[2].strip()
    return meta, text.strip()


def md_to_linkedin(md_text: str) -> str:
    """Convert Markdown to LinkedIn plain-text format."""
    meta, body = strip_frontmatter(md_text)

    lines = body.splitlines()
    output = []
    output.append(LINKEDIN_HEADER)

    # Add title from front matter if available
    if "title" in meta:
        output.append(meta["title"].upper())
        output.append("")

    if "date" in meta:
        output.append(f"Week of {meta['date']}")
        output.append("")

    for line in lines:
        stripped = line.strip()

        # H1 → skip (already in header)
        if stripped.startswith("# ") and not stripped.startswith("## "):
            continue

        # H2 → section header with emoji
        elif stripped.startswith("## "):
            title = stripped[3:].strip()
            emoji = next((v for k, v in EMOJI_MAP.items() if k.lower() in title.lower()), "📌")
            output.append("")
            output.append(f"{emoji} {title.upper()}")
            output.append("")

        # H3 → bold-style item title
        elif stripped.startswith("### "):
            title = stripped[4:].strip()
            output.append(f"► {title}")

        # Bullet points
        elif stripped.startswith("- ") or stripped.startswith("* "):
            output.append(f"  • {stripped[2:].strip()}")

        # Numbered list
        elif re.match(r"^\d+\.\s", stripped):
            output.append(f"  {stripped}")

        # Bold inline → strip markers
        elif "**" in stripped:
            cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
            output.append(cleaned)

        # Inline code → strip backticks
        elif "`" in stripped:
            cleaned = re.sub(r"`(.+?)`", r"\1", stripped)
            output.append(cleaned)

        # Horizontal rule → LinkedIn separator
        elif stripped in ["---", "***", "___"]:
            output.append("─" * 40)

        # Empty line
        elif stripped == "":
            output.append("")

        # Normal paragraph
        else:
            output.append(stripped)

    # Add hashtags from front matter
    if "tags" in meta:
        tags_raw = meta["tags"].strip("[]").split(",")
        hashtags = " ".join(
            f"#{t.strip().strip('\"').replace(' ', '').replace('#', '')}"
            for t in tags_raw
        )
        output.append("")
        output.append("─" * 40)
        output.append(hashtags)

    output.append("")
    output.append("🔗 Full digest with sources and admin actions - link in the comments.")
    output.append("")

    # Collapse excessive blank lines
    result = "\n".join(output)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def main():
    parser = argparse.ArgumentParser(description="Convert digest MD to LinkedIn paste")
    parser.add_argument("input", help="Path to the Hugo Markdown post file")
    parser.add_argument("--output", "-o", default=None,
                        help="Output file path (default: print to stdout)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {input_path} not found.", file=sys.stderr)
        sys.exit(1)

    md_text = input_path.read_text(encoding="utf-8")
    linkedin_text = md_to_linkedin(md_text)
    post_url = f"https://modernworkweekly.com/posts/{input_path.stem}/"

    if args.output:
        Path(args.output).write_text(linkedin_text, encoding="utf-8")
        print(f"LinkedIn paste written to: {args.output}")
        char_count = len(linkedin_text)
        print(f"Character count: {char_count:,} (LinkedIn post limit: 3,000 for posts, 120,000 for articles)")
    else:
        print(linkedin_text)

    print(f"\nPost first, then paste this as the first comment: {post_url}")


if __name__ == "__main__":
    main()
