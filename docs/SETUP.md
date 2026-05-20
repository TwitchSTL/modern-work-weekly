# Setup Guide — Modern Work Weekly

Full walkthrough from bare Proxmox LXC to live site at your domain.
Estimated time: 2–3 hours the first time.

---

## Prerequisites checklist

- [ ] Proxmox 9.1.1 running, accessible on your network
- [ ] Servers VLAN (10.127.31.0/24) configured, LXC can reach internet
- [ ] GitHub account with this repo cloned or forked
- [ ] Cloudflare account (free tier) — create at cloudflare.com
- [ ] Domain registered at Cloudflare Registrar (e.g. `firstlast.dev`, ~$10-12/yr)

---

## Step 1 — Create the LXC in Proxmox

In the Proxmox web UI:

1. Download Ubuntu 24.04 LXC template if not already present:
   `Datacenter → your node → local storage → CT Templates → Download`
   Template: `ubuntu-24.04-standard`

2. Create container:
   - CT ID: pick any available (e.g. 200)
   - Hostname: `mww`
   - Template: ubuntu-24.04-standard
   - Root disk: 8GB minimum (20GB recommended)
   - CPU: 1 core
   - Memory: 512MB RAM, 512MB swap
   - Network:
     - Bridge: your Servers VLAN bridge (vmbr0 or whichever bridges to VLAN 31)
     - IP: `10.127.31.35/24`
     - Gateway: `10.127.31.1` (or your VLAN gateway)
     - DNS: your Pi-hole IP or `1.1.1.1` temporarily

3. Start the container.

---

## Step 2 — Run the bootstrap script

```bash
# SSH into the LXC as root
ssh root@10.127.31.35

# Download and run bootstrap
curl -sO https://raw.githubusercontent.com/yourusername/modern-work-weekly/main/infra/lxc/bootstrap.sh
chmod +x bootstrap.sh
./bootstrap.sh
```

The script installs: Hugo, Caddy, cloudflared, Python 3 + venv, SSH, logrotate.

---

## Step 3 — Set up Cloudflare

### 3a. Register your domain
1. Go to cloudflare.com → sign up (free)
2. Go to `Domain Registration → Register Domains`
3. Search for your domain (e.g. `firstlast.dev`)
4. Purchase (~$10-12/yr, no markup — at-cost pricing)

### 3b. Create the tunnel
```bash
# On the LXC:
cloudflared tunnel login
# Opens a browser URL — visit it, authorize your Cloudflare account

cloudflared tunnel create modern-work-weekly
# Note the tunnel ID from the output — you'll need it

cloudflared tunnel route dns modern-work-weekly firstlast.dev
cloudflared tunnel route dns modern-work-weekly www.firstlast.dev
```

### 3c. Configure the tunnel
```bash
# Copy tunnel config
mkdir -p /etc/cloudflared
cp /opt/modern-work-weekly/repo/infra/cloudflare/tunnel.yml /etc/cloudflared/config.yml

# Edit it — replace YOUR_TUNNEL_ID with the actual ID from step 3b
nano /etc/cloudflared/config.yml
```

### 3d. Install and start the tunnel service
```bash
cloudflared service install
systemctl enable cloudflared
systemctl start cloudflared
systemctl status cloudflared
```

---

## Step 4 — Configure and start Caddy

```bash
# Copy Caddyfile
cp /opt/modern-work-weekly/repo/infra/caddy/Caddyfile /etc/caddy/Caddyfile

# Verify config
caddy validate --config /etc/caddy/Caddyfile

# Start Caddy
systemctl enable caddy
systemctl start caddy
systemctl status caddy
```

---

## Step 5 — Deploy the Hugo site

```bash
# Clone your repo onto the LXC
git clone https://github.com/yourusername/modern-work-weekly /opt/modern-work-weekly/repo

# Build the site manually for the first time
cd /opt/modern-work-weekly/repo/site
hugo --minify --baseURL "https://firstlast.dev"

# Copy built output to Caddy's serve directory
rsync -av public/ /opt/modern-work-weekly/site/public/

# Set permissions
chown -R mww:mww /opt/modern-work-weekly/site/public/
```

Open your browser → `https://firstlast.dev`
If the tunnel is active and Caddy is running, your site is live. 🎉

---

## Step 6 — Set up GitHub Actions for auto-deploy

Every time you push a new digest post to GitHub, the site rebuilds and deploys automatically.

### 6a. Generate a deploy SSH key
```bash
# On the LXC:
ssh-keygen -t ed25519 -C "github-actions-deploy" -f /tmp/deploy_key -N ""
cat /tmp/deploy_key.pub >> /home/mww/.ssh/authorized_keys
chmod 600 /home/mww/.ssh/authorized_keys
chown mww:mww /home/mww/.ssh/authorized_keys

# Copy the private key — you'll paste it into GitHub Secrets
cat /tmp/deploy_key
```

### 6b. Add GitHub Secrets
Go to your repo → `Settings → Secrets and variables → Actions → New repository secret`:

| Secret name | Value |
|---|---|
| `HOMELAB_HOST` | `10.127.31.35` |
| `HOMELAB_USER` | `mww` |
| `HOMELAB_SSH_KEY` | The private key from `/tmp/deploy_key` (full content including BEGIN/END lines) |

### 6c. Test the workflow
Push any change to `site/` in the `main` branch → GitHub Actions tab → watch the build run.

---

## Step 7 — Set up the scraper and digest pipeline

```bash
# Activate venv and install deps
cd /opt/modern-work-weekly/repo/scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Test scraper (single source)
python scraper.py --source Intune
```

### 7b. Add your Anthropic API key

The digest pipeline calls the Claude API. Get a key at [console.anthropic.com](https://console.anthropic.com)
and store it on the LXC — never in the repo:

```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' > /opt/modern-work-weekly/.env
chmod 600 /opt/modern-work-weekly/.env
```

Test the full pipeline:

```bash
python scraper.py          # Accumulate items into pending_draft.json
python digest.py --dry-run # Verify prompt builds correctly (no API call)
python digest.py           # Generate the draft post
```

### 7c. Schedule the weekly cron

```bash
crontab -e
```

Add:
```
55 5 * * 2 /opt/modern-work-weekly/repo/scraper/weekly-run.sh >> /opt/modern-work-weekly/logs/cron.log 2>&1
```

This fires every Tuesday at 5:55 AM (adjust to your timezone).

---

## Step 8 — Firewall notes (your environment)

Since your Proxmox is behind a VLAN with firewall zones, verify:

- LXC (10.127.31.35) can reach `443/TCP` outbound to the internet — for cloudflared tunnel and scraper HTTP requests
- LXC can reach `22/TCP` from wherever your GitHub Actions runner egress IPs are — OR allow from `0.0.0.0/0` on port 22 for the deploy user only (mww), locked to key auth
- No inbound ports need to be opened on your router/firewall — the Cloudflare Tunnel is entirely outbound

GitHub Actions egress IPs: https://api.github.com/meta (under `actions`)

---

## You're done

- Site live at `https://yourdomain.com`
- Pushes to `master` auto-deploy via GitHub Actions
- Scraper + digest run automatically via Tuesday cron (see `docs/WEEKLY_WORKFLOW.md`)
- Dedup state persists in `/opt/modern-work-weekly/repo/state/seen_items.json`
