# Replacing Pi-hole with NextDNS

Since you're using Pi-hole only for ad-blocking (not local hostname resolution), NextDNS is a clean drop-in replacement with zero maintenance overhead.

---

## Why NextDNS over Pi-hole for this use case

| | Pi-hole | NextDNS |
|---|---|---|
| Ad/tracker blocking | ✅ | ✅ (better blocklists) |
| Local hostname resolution | ✅ | ❌ (see note below) |
| Maintenance | Gravity updates, hardware dependency | Zero — cloud managed |
| Per-device filtering | Clunky | Native, per-device profiles |
| Logs/analytics | Local only | Web dashboard, exportable |
| Failover if device dies | Site loses DNS | Automatic (it's cloud) |
| Cost | Free (your hardware) | Free up to 300k queries/month |

**On local hostname resolution:** If you're not using Pi-hole for custom DNS entries like `proxmox.home.lan` or `10.127.31.35 → mww.local`, you don't need to replace that function. If you are, Proxmox's built-in `/etc/hosts` and Caddy handle it fine for the blog use case.

---

## Setup (15 minutes)

### 1. Create a NextDNS account

Go to [nextdns.io](https://nextdns.io) → Sign up (free).

You get a Configuration ID (e.g. `abc123`). This is your unique resolver.

### 2. Configure your blocklists

In the NextDNS dashboard:

**Security tab:**
- Enable Threat Intelligence Feeds
- Enable Google Safe Browsing
- Enable Cryptojacking Protection
- Enable DNS Rebinding Protection

**Privacy tab (blocklists):**
- NextDNS Ads & Trackers Blocklist ✅
- AdGuard DNS filter ✅
- EasyList ✅
- EasyPrivacy ✅
- Steven Black's Hosts ✅

**Parental Controls:** skip (not needed for homelab)

### 3. Point your network at NextDNS

**Option A — Router-level (affects all devices including LXC)**
In your router/firewall DNS settings, replace Pi-hole IP with:
```
45.90.28.0   (NextDNS primary)
45.90.30.0   (NextDNS secondary)
```
Or use your linked configuration DNS:
```
https://dns.nextdns.io/abc123
```

**Option B — Per-device (just the LXC for now)**
On the LXC, edit `/etc/systemd/resolved.conf`:
```ini
[Resolve]
DNS=45.90.28.0 45.90.30.0
DNSOverTLS=yes
FallbackDNS=1.1.1.1 8.8.8.8
```
Then: `systemctl restart systemd-resolved`

### 4. Verify it's working

```bash
# On the LXC
nslookup doubleclick.net
# Should return NXDOMAIN (blocked)

nslookup learn.microsoft.com
# Should resolve normally
```

Check the NextDNS dashboard → Logs tab — you should see queries appearing.

---

## Decommissioning Pi-hole

Once NextDNS is working:

1. Update any devices/DHCP that pointed to the Pi-hole IP
2. Confirm nothing is still querying the Pi-hole (check its query log for 24h)
3. Stop and disable Pi-hole service, or just power down the Pi
4. You now have one less service to patch and maintain

---

## Note for the LXC specifically

The LXC at `10.127.31.35` needs to reach:
- `*.microsoft.com` and `learn.microsoft.com` — for the scraper
- `api.anthropic.com` — for Phase 2 API calls
- `api.cloudflare.com` — for the tunnel
- `github.com` — for git/Actions

All of these are standard FQDN lookups. NextDNS won't block any of them.
