# Modern Work Weekly

**A self-hosted Microsoft 365 / Modern Work change digest — published as a blog, shared to LinkedIn.**

Built and maintained by Ryan Arbuckle. Runs on a Proxmox 9.1.1 homelab, served via Cloudflare Tunnel, published with Hugo.

---

## What this project does

Every week, a Python scraper collects "What's New" updates from Microsoft's official portals across Intune, Entra, Defender XDR, Purview, Teams, Autopatch, and SharePoint. The raw pull is reviewed in Claude.ai (using your existing subscription), turned into a structured digest, and published as:

- A **blog post** on your Hugo site (hosted on your homelab LXC, exposed via Cloudflare Tunnel)
- A **Markdown file** committed to this GitHub repo (version history + backup)
- A **LinkedIn-ready paste** generated from a template script

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
├── linkedin/                 # LinkedIn article formatter
│   ├── formatter.py          # Converts digest MD → LinkedIn paste
│   └── template.md           # LinkedIn article structure template
│
├── site/                     # Hugo site — this IS your blog
│   ├── hugo.toml             # Hugo config
│   ├── content/posts/        # One .md file per weekly digest
│   ├── assets/css/           # Custom styles
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
│   ├── SETUP.md              # Full setup guide (Proxmox → live site)
│   ├── WEEKLY_WORKFLOW.md    # What you do every Monday
│   ├── PHASE2_API.md         # Upgrade path to fully automated pipeline
│   └── DNS_NEXTDNS.md        # Replacing Pi-hole with NextDNS
│
├── .github/
│   └── workflows/
│       └── hugo-build.yml    # GitHub Action: builds Hugo on push
│
├── .gitignore
└── README.md                 # This file
```

---

## Phase 1 (current) — Manual-assisted workflow

```
Monday morning
  1. Run scraper:        cd scraper && python scraper.py
  2. Review output:      state/weekly_draft_YYYY-MM-DD.json
  3. Open Claude.ai →   paste JSON + master prompt → get digest draft
  4. Edit digest:        save to site/content/posts/YYYY-MM-DD.md
  5. Push to GitHub:     git add . && git commit -m "digest: YYYY-MM-DD" && git push
  6. GitHub Action builds Hugo → syncs to LXC
  7. LinkedIn:           python linkedin/formatter.py → paste ready
```

**Estimated time per week:** 30–45 minutes including review and editing.

## Phase 2 (upgrade path) — Fully automated

Add an Anthropic API key → scraper calls Claude directly → digest drafted automatically → you review and push. See `docs/PHASE2_API.md`.

---

## Tech stack

| Component | Tool | Why |
|---|---|---|
| Hosting | Proxmox 9.1.1 LXC (Ubuntu 24.04) | You already have it |
| Web server | Caddy | Auto TLS, minimal config |
| Tunnel | Cloudflare Tunnel | No exposed home IP, free |
| Static site | Hugo | Markdown-native, fast |
| Scraper | Python 3.12 | Portable, easy to extend |
| CI/CD | GitHub Actions | Free, triggers on push |
| DNS filtering | NextDNS (replacing Pi-hole) | Cloud-managed, zero maintenance |

---

## Quick links once deployed

- Blog: `https://RyanArbuckle.dev` (swap your real domain)
- Hugo admin: SSH into `10.127.31.35`
- Scraper logs: `/opt/modern-work-weekly/logs/`
- State file: `/opt/modern-work-weekly/state/seen_items.json`
