#!/bin/bash
# bootstrap.sh — Modern Work Weekly LXC setup
# Run once on a fresh Ubuntu 24.04 LXC on Proxmox.
# Static IP: 10.127.31.35 (configure in Proxmox before running this)
#
# Usage:
#   ssh root@10.127.31.35
#   chmod +x bootstrap.sh && ./bootstrap.sh

set -e

echo "=========================================="
echo "  Modern Work Weekly — LXC Bootstrap"
echo "  Proxmox LXC on 10.127.31.35"
echo "=========================================="

# ── System update ────────────────────────────────────────────────────────────
echo "[1/9] Updating system packages..."
apt-get update -qq && apt-get upgrade -y -qq

# ── Core packages ────────────────────────────────────────────────────────────
echo "[2/9] Installing core packages..."
apt-get install -y -qq \
  curl wget git rsync unzip \
  python3 python3-pip python3-venv \
  ca-certificates gnupg \
  openssh-server \
  cron logrotate

# ── Create deploy user ───────────────────────────────────────────────────────
echo "[3/9] Creating deploy user..."
if ! id -u mww &>/dev/null; then
  useradd -m -s /bin/bash mww
  mkdir -p /home/mww/.ssh
  chmod 700 /home/mww/.ssh
  echo "  Created user: mww"
  echo "  ACTION: Add your GitHub Actions public SSH key to /home/mww/.ssh/authorized_keys"
fi

# ── Directory structure ──────────────────────────────────────────────────────
echo "[4/9] Creating directory structure..."
mkdir -p /opt/modern-work-weekly/{site/public,state,logs,scraper}
chown -R mww:mww /opt/modern-work-weekly

# ── Hugo ─────────────────────────────────────────────────────────────────────
echo "[5/9] Installing Hugo..."
HUGO_VERSION="0.128.0"
HUGO_URL="https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_${HUGO_VERSION}_linux-amd64.tar.gz"
wget -q "$HUGO_URL" -O /tmp/hugo.tar.gz
tar -xzf /tmp/hugo.tar.gz -C /tmp
mv /tmp/hugo /usr/local/bin/hugo
chmod +x /usr/local/bin/hugo
rm /tmp/hugo.tar.gz
hugo version

# ── Caddy ────────────────────────────────────────────────────────────────────
echo "[6/9] Installing Caddy..."
curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key \
  | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/caddy-stable-archive-keyring.gpg] \
  https://dl.cloudsmith.io/public/caddy/stable/deb/debian any-version main" \
  | tee /etc/apt/sources.list.d/caddy-stable.list
apt-get update -qq && apt-get install -y -qq caddy
systemctl enable caddy
echo "  Caddy installed. Configure /etc/caddy/Caddyfile then: systemctl start caddy"

# ── Cloudflare Tunnel (cloudflared) ─────────────────────────────────────────
echo "[7/9] Installing cloudflared..."
ARCH="amd64"
wget -q "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${ARCH}" \
  -O /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared
cloudflared --version
echo "  cloudflared installed. Run 'cloudflared tunnel login' after setting up Cloudflare account."

# ── Python scraper environment ───────────────────────────────────────────────
echo "[8/9] Setting up Python scraper environment..."
python3 -m venv /opt/modern-work-weekly/scraper/.venv
/opt/modern-work-weekly/scraper/.venv/bin/pip install -q \
  requests beautifulsoup4 feedparser lxml
chown -R mww:mww /opt/modern-work-weekly/scraper

# ── SSH for GitHub Actions deployment ───────────────────────────────────────
echo "[9/9] Configuring SSH..."
sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config
systemctl restart ssh

# ── Logrotate for scraper logs ───────────────────────────────────────────────
cat > /etc/logrotate.d/modern-work-weekly << 'EOF'
/opt/modern-work-weekly/logs/*.log {
    weekly
    rotate 12
    compress
    missingok
    notifempty
}
EOF

echo ""
echo "=========================================="
echo "  Bootstrap complete!"
echo "=========================================="
echo ""
echo "  Next steps:"
echo "  1. Copy Caddyfile: cp infra/caddy/Caddyfile /etc/caddy/Caddyfile"
echo "     Then: systemctl start caddy"
echo ""
echo "  2. Set up Cloudflare account at cloudflare.com"
echo "     Buy domain at Cloudflare Registrar (~\$10-12/yr for .dev)"
echo "     Then: cloudflared tunnel login"
echo "     Then: cp infra/cloudflare/tunnel.yml /etc/cloudflared/config.yml"
echo "     Then: cloudflared service install"
echo ""
echo "  3. Add GitHub Actions SSH key:"
echo "     echo 'YOUR_PUBKEY' >> /home/mww/.ssh/authorized_keys"
echo "     chmod 600 /home/mww/.ssh/authorized_keys"
echo "     chown mww:mww /home/mww/.ssh/authorized_keys"
echo ""
echo "  4. Clone the repo onto the LXC:"
echo "     git clone https://github.com/TwitchSTL/modern-work-weekly /opt/modern-work-weekly/repo"
echo ""
echo "  5. See docs/SETUP.md for the full walkthrough."
echo ""
