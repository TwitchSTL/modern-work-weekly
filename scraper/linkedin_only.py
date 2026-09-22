#!/usr/bin/env python3
"""
linkedin_only.py — Regenerate ONLY the LinkedIn newsletter draft, announcement
post, and tag candidates for an already-published week, without touching the
technical post, Executive's Guide, or search index.

Why this exists: digest.py wraps LinkedIn generation in a non-fatal
try/except (see main()) — if it throws, the run still publishes the
technical post/exec guide/search index and just logs a warning. That's
what happened for 2026-09-22: the post published on schedule but
state/linkedin_draft_2026-09-22.txt and state/linkedin_post_2026-09-22.txt
never got written. A full `digest.py --draft <archived>` regen would
re-roll Top 5 (it's a fresh, non-deterministic Claude call every run) and
could diverge from the post that's already live — this script reuses the
already-published post's Top 5 instead, exactly like the normal pipeline
does for the LinkedIn steps.

Usage:
    cd /opt/modern-work-weekly/repo/scraper
    source /opt/modern-work-weekly/scraper/.venv/bin/activate
    python3 linkedin_only.py --week 2026-09-22

Requires (same as the normal pipeline):
    - site/content/posts/<week>.md already published
    - state/archive/pending_draft_<week>.json already archived (digest.py
      archives it right after a successful run, regardless of whether the
      LinkedIn steps succeeded)
    - ANTHROPIC_API_KEY set (same .env as digest.py)
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import digest  # noqa: E402
from dotenv import load_dotenv  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", required=True, help="Week date, e.g. 2026-09-22")
    args = parser.parse_args()
    week_of = args.week

    # digest.py only loads .env inside its own main(), which we never call —
    # replicate that step here or anthropic.Anthropic() can't find the key.
    if digest.ENV_FILE.exists():
        load_dotenv(digest.ENV_FILE)
    else:
        load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(f"ERROR: ANTHROPIC_API_KEY not set and not found in {digest.ENV_FILE}")
        sys.exit(1)

    post_path = digest.POSTS_DIR / f"{week_of}.md"
    if not post_path.exists():
        print(f"ERROR: published post not found at {post_path}")
        sys.exit(1)
    content = post_path.read_text(encoding="utf-8")

    archived_draft_path = digest.STATE_DIR / "archive" / f"pending_draft_{week_of}.json"
    if not archived_draft_path.exists():
        print(f"ERROR: archived draft not found at {archived_draft_path}")
        print("This script needs the raw item pool (grouped_items) to build")
        print("the LinkedIn prompt's ADDITIONAL ITEMS section and bylines —")
        print("the published post markdown alone isn't enough.")
        sys.exit(1)
    draft = json.loads(archived_draft_path.read_text(encoding="utf-8"))

    linkedin_draft_path = None
    li_content = ""  # populated on success; announcement hashtag matching
    # below also scans this, so it must exist even if this block fails.
    try:
        li_prompt = digest.build_linkedin_prompt(draft, week_of, content)
        li_content = digest.clean_dashes(digest.call_claude_linkedin(li_prompt))
        li_content = digest.append_linkedin_closer(li_content, content)
        linkedin_draft_path = digest.write_linkedin_draft(li_content, week_of)
    except Exception as e:
        print(f"LinkedIn draft generation failed: {e}")

    announcement_path = None
    try:
        top5 = digest.extract_top5(content)
        ann_prompt = digest.build_announcement_prompt(top5, week_of)
        ann_content = digest.clean_dashes(digest.call_claude_announcement(ann_prompt))
        tags = digest.extract_post_tags(content)
        hashtag_source = f"{ann_content}\n{li_content}"
        hashtags = " ".join(digest.build_hashtags(tags, text=hashtag_source))
        post_url = digest.modernworkweekly_url(f"posts/{week_of}")
        ann_content = (
            f"{ann_content}\n\n{hashtags}\n\n"
            f"[Post this first. Immediately after it publishes, add this as the "
            f"FIRST comment — do not put it in the body, do not add a second link: "
            f"{post_url}]"
        )
        announcement_path = digest.write_announcement_draft(ann_content, week_of)
    except Exception as e:
        print(f"LinkedIn announcement post generation failed: {e}")

    tag_candidates_path = None
    try:
        tag_candidates = digest.collect_tag_candidates(digest.extract_top5(content), draft)
        if tag_candidates:
            tag_candidates_path = digest.write_tag_candidates(tag_candidates, week_of)
    except Exception as e:
        print(f"Tag-candidate collection failed: {e}")

    print(f"\n{'='*60}")
    if linkedin_draft_path:
        print(f"  LinkedIn draft:      {linkedin_draft_path}")
    if announcement_path:
        print(f"  LinkedIn post:       {announcement_path}")
    if tag_candidates_path:
        print(f"  Tag candidates:      {tag_candidates_path}")
    if not (linkedin_draft_path or announcement_path):
        print("  Nothing generated — check the errors above.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
