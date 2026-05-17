# Phase 2 — Fully Automated Pipeline

When you're ready to remove the manual Claude.ai step and run end-to-end automatically, this is the upgrade path. Estimated additional cost: ~$0.50/week.

---

## What changes in Phase 2

| Step | Phase 1 (current) | Phase 2 (automated) |
|---|---|---|
| Scraper | Manual trigger on LXC | systemd timer, every Monday 6am |
| Digest generation | Paste JSON into Claude.ai | Scraper calls Anthropic API directly |
| Post creation | You copy/paste and edit | Script writes draft .md file |
| Push | Manual `git push` | Still manual — you review before publishing |

Phase 2 removes the Claude.ai paste step. You still review and push the draft — full automation (auto-push without review) is Phase 3 if you ever want it.

---

## Step 1 — Get an Anthropic API key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up / sign in
3. Go to `API Keys → Create Key`
4. Name it `modern-work-weekly`
5. Copy the key — you only see it once

---

## Step 2 — Store the key on the LXC

Never put the API key in the repo. Store it in an env file on the LXC only:

```bash
# On the LXC
echo 'ANTHROPIC_API_KEY=sk-ant-...' > /opt/modern-work-weekly/.env
chmod 600 /opt/modern-work-weekly/.env
chown mww:mww /opt/modern-work-weekly/.env
```

---

## Step 3 — Add the API call to the scraper

Add this to `scraper/requirements.txt`:
```
anthropic==0.28.0
```

Then add this function to `scraper/scraper.py`:

```python
import anthropic
import os
from pathlib import Path

def load_env():
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

def generate_digest_via_api(draft: dict, week_date: str) -> str:
    """Call Claude API to generate the digest from the scraped draft."""
    load_env()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set. See docs/PHASE2_API.md.")

    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = """You are an enterprise automation agent producing a weekly
Microsoft Modern Work change digest for engineers, architects, and admins.
Your output must follow this exact structure:
- Top 5 Changes (ranked by urgency/impact)
- Endpoint Management Highlights
- Identity & Access Highlights
- Security & Compliance Highlights
- AI & Automation Highlights
- Recommended Actions for the Week
- Graph / API / Automation Hooks to Explore
- Hashtags

Tone: professional, concise, slightly witty. No marketing fluff.
Focus on: operational impact, policy/config changes, risk/compliance, automation opportunities.
Format output as Markdown suitable for a Hugo blog post."""

    user_message = f"""Generate this week's Modern Work Weekly digest.
Week of: {week_date}
Total new items: {draft['total_new_items']}
Sources checked: {', '.join(draft['sources_checked'])}

Raw scraped items (grouped by category):
{json.dumps(draft['grouped_items'], indent=2)}

Produce the full digest in Markdown format."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": user_message}],
        system=system_prompt,
    )

    return message.content[0].text
```

Then call it in `run_scraper()` after saving the draft JSON:

```python
    # Phase 2: generate digest automatically
    if os.environ.get("ANTHROPIC_API_KEY"):
        log.info("Calling Claude API to generate digest draft...")
        digest_md = generate_digest_via_api(draft, run_date)
        post_path = BASE_DIR / "site" / "content" / "posts" / f"{run_date}.md"
        # Write Hugo front matter + digest
        front_matter = f"""---
title: "Modern Work Weekly — Week of {run_date}"
date: {run_date}
description: "Auto-generated draft — review before publishing."
categories: ["Weekly Digest"]
draft: true
---

{digest_md}
"""
        post_path.write_text(front_matter)
        log.info(f"Digest draft written → {post_path}")
        log.info("Review the draft, change 'draft: true' to 'draft: false', then git push.")
```

---

## Step 4 — Set up systemd timer for Monday 6am runs

```bash
# /etc/systemd/system/modern-work-weekly.service
[Unit]
Description=Modern Work Weekly scraper
After=network-online.target

[Service]
Type=oneshot
User=mww
WorkingDirectory=/opt/modern-work-weekly/scraper
ExecStart=/opt/modern-work-weekly/scraper/.venv/bin/python scraper.py
EnvironmentFile=/opt/modern-work-weekly/.env
StandardOutput=append:/opt/modern-work-weekly/logs/scraper_systemd.log
StandardError=append:/opt/modern-work-weekly/logs/scraper_systemd.log
```

```bash
# /etc/systemd/system/modern-work-weekly.timer
[Unit]
Description=Run Modern Work Weekly scraper every Monday at 6am
Requires=modern-work-weekly.service

[Timer]
OnCalendar=Mon *-*-* 06:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl daemon-reload
systemctl enable modern-work-weekly.timer
systemctl start modern-work-weekly.timer
systemctl list-timers | grep modern
```

---

## Expected cost

| Model | Input cost | Output cost | Est. per run | Est. per year |
|---|---|---|---|---|
| claude-sonnet-4 | $3/M tokens | $15/M tokens | ~$0.30–0.80 | ~$15–40 |

For 20,000 input tokens + 4,000 output tokens:
- Input: $0.06
- Output: $0.06
- **Total per run: ~$0.12–0.50** (lower end if sources are quiet)

Set a spend limit at console.anthropic.com → Billing → Spend limits to cap at $5/month for safety.
