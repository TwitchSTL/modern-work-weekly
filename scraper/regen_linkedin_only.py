#!/usr/bin/env python3
"""One-off: regenerate only the LinkedIn draft for a given week, reusing the
existing (already-correct) post on disk instead of calling Claude for it again.

Usage: python regen_linkedin_only.py YYYY-MM-DD

Takes the week as a CLI arg rather than a hardcoded constant -- editing a
hardcoded WEEK in place caused a real merge conflict on 2026-07-21 (local
edit on the LXC collided with an unrelated fix pushed to this same file),
and left a stale week value in git history that had to be remembered and
changed back. A CLI arg has no state to forget or collide over."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import digest

if len(sys.argv) != 2:
    sys.exit("Usage: python regen_linkedin_only.py YYYY-MM-DD")
WEEK = sys.argv[1]

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

li_prompt = digest.build_linkedin_prompt(draft, week_of, content)
li_content = digest.call_claude_linkedin(li_prompt)
# No hashtags — this is the newsletter article body, not the separate
# announcement/teaser post. See feedback_linkedin_hashtags memory.
li_content = digest.linkify_linkedin_draft(li_content, content)

path = digest.write_linkedin_draft(li_content, week_of)
print(f"LinkedIn draft written → {path}")
