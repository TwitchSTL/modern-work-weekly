#!/usr/bin/env python3
"""One-off: regenerate only the LinkedIn draft for a given week, reusing the
existing (already-correct) post on disk instead of calling Claude for it again."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import digest

WEEK = "2026-06-23"

if digest.ENV_FILE.exists():
    from dotenv import load_dotenv
    load_dotenv(digest.ENV_FILE)
if not os.environ.get("ANTHROPIC_API_KEY"):
    sys.exit("ANTHROPIC_API_KEY not set")

draft_path = digest.ARCHIVE_DIR / f"pending_draft_{WEEK}.json"
draft = digest.load_draft(draft_path)
week_of = draft.get("week_of", WEEK)

post_path = digest.POSTS_DIR / f"{week_of}.md"
content = post_path.read_text()  # existing, already-correct post — NOT regenerated

li_prompt = digest.build_linkedin_prompt(draft, week_of)
li_content = digest.call_claude_linkedin(li_prompt)
li_content = digest.linkify_linkedin_draft(li_content, content)
hashtags = digest.build_hashtags(digest.extract_post_tags(content))
li_content = li_content.rstrip() + "\n\n" + " ".join(hashtags)

path = digest.write_linkedin_draft(li_content, week_of)
print(f"LinkedIn draft written → {path}")
