# Setup Guide — Modern Work Weekly

Full walkthrough from bare Proxmox LXC to live site at your domain.
Estimated time: 2–3 hours the first time.

---

## Prerequisites checklist

- [ ] Proxmox running, accessible on your network
- [ ] LXC can reach the internet (outbound 443/TCP at minimum)
- [ ] GitHub account with this repo cloned or forked
- [ ] Cloudflare account (free tier) — [cloudflare.com](https://cloudflare.com)
- [ ] Domain registered and managed in Cloudflare (e.g. `yourdomain.com`)
- [ ] Anthropic API key — [console.anthropic.com](https://console.anthropic.com)

---

## Step 1 — Create the LXC in Proxmox

In the Proxmox web UI:

1. Download the Ubuntu 24.04 LXC template if not already present:
   `Datacenter → your node → local storage → CT Templates → Download`
   Template: `ubuntu-24.04-standard`

2. Create container:
   - CT ID: pick any available
   - Hostname: `mww`
   - Template: ubuntu-24.04-standard
   - Root disk: 8 GB minimum (20 GB recommended)
   - CPU: 1 core
   - Memory: 512 MB RAM, 512 MB swap
   - Network: set a static IP and gateway appropriate for your network

3. Start the container.

---

## Step 2 — Run the bootstrap script

```bash
# SSH into the LXC as root
ssh root@<your-lxc-ip>

# Download and run bootstrap
curl -sO https://raw.githubusercontent.com/TwitchSTL/modern-work-weekly/main/infra/lxc/bootstrap.sh
chmod +x bootstrap.sh
./bootstrap.sh
```

The script installs: Hugo, Caddy, cloudflared, Python 3 + venv tools, logrotate.

---

## Step 3 — Clone the repo

```bash
git clone https://github.com/TwitchSTL/modern-work-weekly /opt/modern-work-weekly/repo
```

---

## Step 4 — Set up Cloudflare Tunnel

### 4a. Authenticate and create the tunnel

```bash
cloudflared tunnel login
# Opens a browser URL — visit it and authorize your Cloudflare account

cloudflared tunnel create modern-work-weekly
# Note the Tunnel ID from the output — you'll need it next
```

### 4b. Add DNS routes in your Cloudflare dashboard

In the Cloudflare dashboard for your domain, add CNAME records pointing to your tunnel:

| Type | Name | Target |
|---|---|---|
| CNAME | `@` (apex) | `<tunnel-id>.cfargotunnel.com` |
| CNAME | `www` | `<tunnel-id>.cfargotunnel.com` |

Enable **Proxied** (orange cloud) on both records.

> **Note:** `cloudflared tunnel route dns` may create records in the wrong zone if your
> tunnel was authorized under a different domain. Use the dashboard to be certain.

### 4c. Configure the tunnel

```bash
mkdir -p /etc/cloudflared
cp /opt/modern-work-weekly/repo/infra/cloudflare/tunnel.yml /etc/cloudflared/config.yml
nano /etc/cloudflared/config.yml
# Replace YOUR_TUNNEL_ID with the actual ID from step 4a
```

### 4d. Install and start the tunnel service

```bash
cloudflared service install
systemctl enable cloudflared
systemctl start cloudflared
systemctl status cloudflared
```

---

## Step 5 — Configure and start Caddy

```bash
cp /opt/modern-work-weekly/repo/infra/caddy/Caddyfile /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile
systemctl enable caddy
systemctl start caddy
systemctl status caddy
```

---

## Step 6 — Build and deploy the Hugo site

```bash
cd /opt/modern-work-weekly/repo/site
hugo --minify --baseURL "https://yourdomain.com"

rsync -av public/ /opt/modern-work-weekly/site/public/
chown -R www-data:www-data /opt/modern-work-weekly/site/public/
```

Open your browser → `https://yourdomain.com`. If the tunnel is active and Caddy
is running, your site is live.

---

## Step 7 — Set up auto-deploy

Deployment is **pull-based**, not push-based: GitHub Actions only runs a CI build
check on push to `main` (touching `site/**`) so you catch a broken Hugo build before
it reaches the LXC — see `.github/workflows/hugo-build.yml`. No SSH keys or repo
secrets are needed for this.

The actual deploy happens on the LXC itself via `scraper/deploy.sh`, which polls
GitHub every 5 minutes:

```bash
chmod +x /opt/modern-work-weekly/repo/scraper/deploy.sh
crontab -e
```

Add:

```
# Pull + rebuild + deploy — every 5 minutes
*/5 * * * * /opt/modern-work-weekly/repo/scraper/deploy.sh >> /var/log/mww-deploy.log 2>&1
```

`deploy.sh` pulls `origin main`; if new commits landed, it runs `hugo --minify` and
rsyncs `site/public/` to the web root. If nothing changed, it exits quietly. Logs land
in `/var/log/mww-deploy.log`.

> **Note:** `weekly-run.sh` (Step 8) builds and deploys immediately after it pushes
> the Tuesday digest, rather than waiting on this cron — since the LXC just made the
> commit itself, `deploy.sh`'s next run would see "already up to date" and skip.

### Test it

Push any change touching `site/**` to `main` → within 5 minutes, check
`/var/log/mww-deploy.log` for a "New commits detected... Deploy done" entry, and
confirm the change is live at your domain.

---

## Step 8 — Set up the scraper and digest pipeline

### 8a. Create the venv

The venv lives outside the repo so it persists across repo resets and `git pull` operations:

```bash
mkdir -p /opt/modern-work-weekly/scraper
cd /opt/modern-work-weekly/scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r /opt/modern-work-weekly/repo/scraper/requirements.txt
```

### 8b. Add your Anthropic API key

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' > /opt/modern-work-weekly/.env
chmod 600 /opt/modern-work-weekly/.env
```

### 8c. Configure git identity on the LXC

Automated commits need an identity set:

```bash
git config --global user.name "mww-bot"
git config --global user.email "bot@yourdomain.com"
```

### 8d. Test the pipeline

```bash
source /opt/modern-work-weekly/scraper/.venv/bin/activate
cd /opt/modern-work-weekly/repo/scraper

python scraper.py --source Intune          # Test single source
python digest.py --dry-run                 # Verify prompt builds correctly (no API call)
python digest.py                           # Full run — generates digest + Executive's Guide + LinkedIn draft
```

### 8e. Schedule the crons

```bash
chmod +x /opt/modern-work-weekly/repo/scraper/weekly-run.sh
chmod +x /opt/modern-work-weekly/repo/scraper/health-run.sh
crontab -e
```

Add these two entries (alongside the `deploy.sh` entry you already added in Step 7,
for three cron jobs total):

```
# Full digest pipeline — every Tuesday at 5:55 AM CST (11:55 UTC)
55 11 * * 2 /opt/modern-work-weekly/repo/scraper/weekly-run.sh

# Known issues refresh — every 8 hours
0 */8 * * * /opt/modern-work-weekly/repo/scraper/health-run.sh
```

Verify all three are registered:
```bash
crontab -l
```

---

## Step 9 — Firewall notes

Verify your LXC can reach:
- `443/TCP` outbound to the internet — for Cloudflare Tunnel, scraper HTTP requests, and Claude API
- `22/TCP` inbound from GitHub Actions runner IPs — for the deploy SSH step (see [GitHub's IP list](https://api.github.com/meta) under `actions`)

No inbound ports need to be opened on your router — the Cloudflare Tunnel is entirely outbound.

---

## You're done

| What | Where |
|---|---|
| Live site | `https://yourdomain.com` |
| Digest posts auto-publish | Every Tuesday ~5:55 AM CST |
| Known issues auto-refresh | Every 8 hours |
| Pushes to `main` auto-deploy | Via `deploy.sh` cron on the LXC (within 5 min) |
| GitHub Actions | CI build check only — does not deploy |
| Dedup state | `/opt/modern-work-weekly/repo/state/seen_items.json` |
| Logs | `/var/log/mww-weekly.log`, `/var/log/mww-deploy.log`, and `/opt/modern-work-weekly/logs/` |

See [`docs/WEEKLY_WORKFLOW.md`](WEEKLY_WORKFLOW.md) for the ongoing weekly process.
