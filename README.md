# Modern Work Weekly

[![Hugo Build](https://github.com/TwitchSTL/modern-work-weekly/actions/workflows/hugo-build.yml/badge.svg)](https://github.com/TwitchSTL/modern-work-weekly/actions/workflows/hugo-build.yml)
[![Site](https://img.shields.io/badge/site-ryanarbuckle.dev-blue?style=flat)](https://ryanarbuckle.dev)
[![Support on Ko-fi](https://img.shields.io/badge/support-Ko--fi-ff5e5b?logo=ko-fi&logoColor=white)](https://ko-fi.com/ryanarbuckle)

> A self-hosted, fully automated Microsoft 365 change digest — scraped, drafted by Claude, and published weekly as a Hugo blog.

---

## What this is

**Modern Work** is Microsoft's framework for secure, cloud-connected productivity — built around Microsoft 365 and underpinned by the **Zero Trust** security model. Modern Work engineers are responsible for deploying and hardening the full stack: identity through Entra ID, device compliance through Intune, data protection through Purview, threat detection through Defender, and network access through Global Secure Access.

Microsoft ships updates across all of it continuously. **Modern Work Weekly** scrapes the official portals, uses the Claude API to draft a structured digest, and publishes it every Tuesday — so engineers can stay current without spending hours across portals tracking it themselves.

No marketing. No executive summaries. Operational signal only.

---

## How it works

```
Every Tuesday at 5:55 AM CST (automated cron on LXC)
  ┌─────────────────────────────────────────────────────────┐
  │  scraper.py   →  Fetches 15+ Microsoft portals          │
  │                  Deduplicates against seen_items.json   │
  │                  Appends new items to pending_draft.json │
  │                  Writes known issues to health.json     │
  │                                                         │
  │  digest.py    →  Reads pending_draft.json               │
  │                  Calls Claude API (claude-sonnet-4-6)   │
  │                  Writes site/content/posts/YYYY-MM-DD.md│
  │                  Archives pending_draft.json            │
  │                                                         │
  │  git push     →  GitHub Actions builds the Hugo site    │
  │                  Deployed via Cloudflare Tunnel         │
  └─────────────────────────────────────────────────────────┘
```

**Rolling draft:** The scraper accumulates new items into `pending_draft.json` across every run. When the Tuesday digest fires, it consumes everything since the last publish — so nothing gets lost between runs.

---

## Sources scraped

| Category | Sources |
|---|---|
| Identity & Access | Entra ID |
| Endpoint Management | Intune, Autopilot, Windows 365 |
| Security | Defender XDR, Defender for Endpoint, Defender for Office 365 |
| Collaboration | Teams, SharePoint / OneDrive, Exchange Online |
| Data | Purview |
| Network | Global Secure Access |
| Cross-platform | Microsoft 365 Roadmap, Microsoft Security Blog, Agent 365 |
| Known Issues | Intune, Autopilot, Windows 365, Defender for Endpoint, Defender XDR, Purview, Entra ID, Teams, Windows Release Health |

---

## Repository layout

```
modern-work-weekly/
├── scraper/
│   ├── scraper.py            # Fetches portals, deduplicates, builds pending draft
│   ├── digest.py             # Calls Claude API, writes Hugo post, archives draft
│   ├── sources.py            # All source URLs, selectors, and health flags
│   ├── weekly-run.sh         # Tuesday cron entrypoint — pull → scrape → draft → push
│   └── requirements.txt
│
├── state/                    # Persisted on LXC — gitignored
│   ├── seen_items.json       # Dedup tracker
│   ├── pending_draft.json    # Rolling accumulator (cleared after each publish)
│   ├── weekly_draft_*.json   # Per-run snapshots (kept for reference)
│   └── archive/              # Archived pending drafts post-publish
│
├── site/                     # Hugo site
│   ├── content/posts/        # One .md file per weekly digest
│   ├── data/
│   │   ├── health.json       # Known issues — rendered in sidebar
│   │   └── deadlines.json    # ZT deadline calendar data
│   ├── layouts/              # Hugo templates (3-column digest layout)
│   ├── static/css/           # Custom styles
│   └── static/js/            # collapsible.js, calendar.js, sidebar-dates.js
│
├── infra/
│   ├── lxc/bootstrap.sh      # Fresh Ubuntu 24.04 LXC setup
│   ├── caddy/Caddyfile        # Reverse proxy config
│   └── cloudflare/tunnel.yml # Cloudflare Tunnel config
│
├── docs/
│   ├── SETUP.md              # Full setup guide
│   ├── WEEKLY_WORKFLOW.md    # Pipeline reference
│   └── PHASE2_API.md         # Claude API integration notes
│
└── .github/
    ├── FUNDING.yml           # Ko-fi sponsor link
    └── workflows/
        └── hugo-build.yml    # Build + deploy on push to site/**
```

---

## Tech stack

| Component | Tool |
|---|---|
| Hosting | Ubuntu 24.04 LXC (Proxmox) |
| Web server | Caddy |
| Tunnel | Cloudflare Tunnel |
| Static site | Hugo |
| Scraper | Python 3.12 — requests, BeautifulSoup, feedparser |
| Digest drafting | Claude API (claude-sonnet-4-6) |
| CI/CD | GitHub Actions |

---

## Requirements

- Python 3.12+ with dependencies from `scraper/requirements.txt`
- `ANTHROPIC_API_KEY` in `/opt/modern-work-weekly/.env`
- Hugo extended v0.128+
- Cloudflare Tunnel configured for your domain

---

## Support

This project is free and open. If it saves you time, [contributions on Ko-fi](https://ko-fi.com/ryanarbuckle) help offset the API costs and keep it going.
