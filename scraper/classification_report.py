#!/usr/bin/env python3
"""
classification_report.py — quick health check on the classify_item() taxonomy.

Reads state/classification_stats.json (written by scraper.py's
write_classification_stats() after every scraper run) and prints per-category
totals plus the fallback rate, so a keyword gap shows up as a number in one
command instead of requiring manual inspection of pending_draft.json.

Usage:
    python classification_report.py                # last 8 runs
    python classification_report.py --runs 20       # last 20 runs
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

STATE_DIR = Path(__file__).resolve().parent.parent / "state"
STATS_FILE = STATE_DIR / "classification_stats.json"


def main():
    parser = argparse.ArgumentParser(description="Classification taxonomy health report")
    parser.add_argument(
        "--runs", type=int, default=8,
        help="Number of most recent scraper runs to summarize (default: 8)",
    )
    args = parser.parse_args()

    if not STATS_FILE.exists():
        print(f"No stats file found at {STATS_FILE} yet — run scraper.py at least once.")
        return

    with open(STATS_FILE) as f:
        history = json.load(f).get("history", [])

    if not history:
        print("Stats file exists but has no recorded runs yet.")
        return

    recent = history[-args.runs:]

    totals = defaultdict(int)
    total_items = 0
    total_fallback = 0
    fallback_examples = []

    print(f"\n{'='*70}")
    print(f"Classification report — last {len(recent)} run(s)")
    print(f"{'='*70}\n")
    print(f"{'run_date':<12} {'items':>6} {'fallback':>9} {'fallback %':>11}")
    for entry in recent:
        n = entry.get("total_items", 0)
        fb = entry.get("fallback_count", 0)
        pct = f"{(fb / n * 100):.0f}%" if n else "n/a"
        print(f"{entry.get('run_date', '?'):<12} {n:>6} {fb:>9} {pct:>11}")
        total_items += n
        total_fallback += fb
        for cat, count in entry.get("by_category", {}).items():
            totals[cat] += count
        fallback_examples.extend(entry.get("fallback_titles", []))

    print(f"\n{'-'*70}")
    if total_items:
        print(
            f"Totals across {len(recent)} run(s): {total_items} items, "
            f"{total_fallback} fallback ({(total_fallback / total_items * 100):.0f}%)"
        )
    else:
        print("No items recorded in this range.")

    print(f"\n{'category':<32} {'items':>8} {'share':>8}")
    for cat, count in sorted(totals.items(), key=lambda kv: -kv[1]):
        share = f"{(count / total_items * 100):.0f}%" if total_items else "n/a"
        print(f"{cat:<32} {count:>8} {share:>8}")

    if fallback_examples:
        print(f"\nRecent fallback (unmatched) titles — candidates for new keywords:")
        for t in fallback_examples[-10:]:
            print(f"  - {t[:90]}")


if __name__ == "__main__":
    main()
