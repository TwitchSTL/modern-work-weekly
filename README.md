# Modern Work Weekly

**A self-hosted Microsoft 365 / Modern Work change digest — published as a blog.**

Built and maintained by Ryan Arbuckle. Runs on a homelab LXC, served via Cloudflare Tunnel, published with Hugo.

---

## What this project does

Every week, a Python scraper collects "What's New" updates from Microsoft's official portals across Intune, Entra, Defender XDR, Purview, Teams, the Microsoft Security Blog, the M365 Roadmap, Agent 365, and SharePoint. The raw pull is reviewed in Claude.ai, turned into a structured digest, and published as:

- A **blog post** at [ryanarbuckle.dev](https://ryanarbuckle.dev)
- A **Markdown file** committed to this GitHub repo (version history + backup)

---

## Repository layout

```
modern-work-weekly/
├── scraper/                  # Python scraper — collects raw MS update data
│   ├── scraper.py            # Main scraper script
│   ├── sources.py            # Source URLs and selectors per portal
│   ├── requirements.txt      # Python dependencies
│   └── README.md             # Scraper-specific docs
│
├── state/                    # Persisted state — stays on LXC, never pushed to GitHub
│   └── seen_items.json       # Dedup tracker (gitignored)
│
├── linkedin/                 # LinkedIn article formatter (in progress)
│   ├── formatter.py          # Converts digest MD → LinkedIn paste
│   └── template.md           # LinkedIn article structure template
│
├── site/                     # Hugo site
│   ├── hugo.toml             # Hugo config
│   ├── content/posts/        # One .md file per weekly digest
│   ├── static/css/           # Custom styles
│   ├── layouts/              # Hugo templates
│   └── archetypes/           # New post template
│
├── infra/
│   ├── lxc/
│   │   └── bootstrap.sh      # Run once on a fresh Ubuntu 24.04 LXC
│   ├── caddy/
│   │   └── Caddyfile         # Reverse proxy config
│   └── cloudflare/
│       └── tunnel.yml        # Cloudflare Tunnel config
│
├── docs/
│   ├── SETUP.md              # Full setup guide (LXC → live site)
│   ├── WEEKLY_WORKFLOW.md    # What you do every Monday
│   ├── PHASE2_API.md         # Upgrade path to fully automated pipeline
│   └── DNS_NEXTDNS.md        
│
├── .github/
│   └── workflows/
│       └── hugo-build.yml    # GitHub Action: validates Hugo build on push
│
├── .gitignore
└── README.md                 # This file
```

---

## Phase 1 (current) — Manual-assisted workflow

```
Monday morning
  1. Run scraper:        python scraper/scraper.py
  2. Review output:      state/weekly_draft_YYYY-MM-DD.json
  3. Open Claude.ai →   paste JSON + master prompt → get digest draft
  4. Edit digest:        save to site/content/posts/YYYY-MM-DD.md
  5. Push to GitHub:     git add . && git commit -m "digest: YYYY-MM-DD" && git push
  6. Site rebuilds automatically within 5 minutes via LXC cron job
```

**Estimated time per week:** 30–45 minutes including review and editing.

## Phase 2 (upgrade path) — Fully automated

Add an Anthropic API key → scraper calls Claude directly → digest drafted automatically → you review and push. See `docs/PHASE2_API.md`.

---

## Tech stack

| Component | Tool |
|---|---|
| Hosting | LXC on Ubuntu 24.04 |
| Web server | Caddy |
| Tunnel | Cloudflare Tunnel |
| Static site | Hugo |
| Scraper | Python 3.12 |
| CI/CD | GitHub Actions |

---

## Quick links

- Blog: [ryanarbuckle.dev](https://ryanarbuckle.dev)
- Scraper logs: `/opt/modern-work-weekly/logs/`
- State file: `/opt/modern-work-weekly/state/seen_items.json`
