"""
sources.py — Microsoft portal source definitions for the scraper.

Each source has:
  - name: display name
  - url: the "What's New" or release notes page
  - cadence: how often it updates
  - category: default classification bucket
  - rss: RSS feed URL if available (preferred over HTML scraping)
  - selector: CSS selector for HTML fallback (if no RSS)
  - health: True if this is a known-issues/service-health source (routed separately)
"""

SOURCES = [
    {
        "name": "Intune",
        "url": "https://learn.microsoft.com/en-us/intune/intune-service/fundamentals/whats-new",
        "cadence": "weekly",
        "category": "Endpoint Management",
        "rss": None,
        "selector": "h2, h3, p",
    },
    {
        "name": "Defender XDR",
        "url": "https://learn.microsoft.com/en-us/defender-xdr/whats-new",
        "cadence": "monthly",
        "category": "Security & Compliance",
        "rss": None,
        "selector": "h2, h3, p",
    },
    {
        "name": "Entra ID",
        "url": "https://learn.microsoft.com/en-us/entra/fundamentals/whats-new",
        "cadence": "irregular",
        "category": "Identity & Access",
        "rss": None,
        "selector": "h2, h3, p",
    },
    {
        "name": "Teams",
        "url": "https://learn.microsoft.com/en-us/officeupdates/teams-admin",
        "cadence": "rolling",
        "category": "Collaboration & Productivity",
        "rss": None,
        "selector": "h2, h3, p",
    },
    {
        "name": "Microsoft Security Blog (Zero Trust)",
        "url": "https://www.microsoft.com/en-us/security/blog/",
        "cadence": "rolling",
        "category": "Security & Compliance",
        "rss": "https://www.microsoft.com/en-us/security/blog/feed/",
        "selector": None,
    },
    {
        "name": "Purview",
        "url": "https://learn.microsoft.com/en-us/purview/whats-new",
        "cadence": "monthly",
        "category": "Security & Compliance",
        "rss": None,
        "selector": "h2, h3, p",
    },
    {
        "name": "SharePoint / OneDrive",
        "url": "https://support.microsoft.com/en-us/office/what-s-new-in-sharepoint-02449ef0-027e-4089-8717-f0ae7ea58029",
        "cadence": "rolling",
        "category": "Collaboration & Productivity",
        "rss": None,
        "selector": "h2, h3, p",
    },
    {
        "name": "Microsoft 365 Roadmap",
        "url": "https://www.microsoft.com/en-us/microsoft-365/roadmap",
        "cadence": "rolling",
        "category": "Cross-platform",
        "rss": "https://www.microsoft.com/en-us/microsoft-365/RoadmapFeatureRSS",
        "selector": None,
    },
    {
        "name": "Agent 365",
        "url": "https://techcommunity.microsoft.com/category/microsoft365/blog/agent-365-blog",
        "cadence": "monthly",
        "category": "Automation & AI",
        "rss": None,
        "selector": "h2, h3, p",
    },
    {
        "name": "Defender for Endpoint",
        "url": "https://learn.microsoft.com/en-us/defender-endpoint/whats-new-in-microsoft-defender-endpoint",
        "cadence": "monthly",
        "category": "Visibility & Automation",
        "rss": None,
        "selector": "h2, h3, p",
    },
    {
        "name": "Defender for Office 365",
        "url": "https://learn.microsoft.com/en-us/defender-office-365/defender-for-office-365-whats-new",
        "cadence": "monthly",
        "category": "Visibility & Automation",
        "rss": None,
        "selector": "h2, h3, p",
    },
    {
        "name": "Exchange Online",
        "url": "https://learn.microsoft.com/en-us/exchange/whats-new",
        "cadence": "monthly",
        "category": "Apps",
        "rss": None,
        "selector": "h2, h3, p",
    },
    {
        "name": "Windows 365",
        "url": "https://learn.microsoft.com/en-us/windows-365/whats-new",
        "cadence": "monthly",
        "category": "Devices",
        "rss": None,
        "selector": "h2, h3, p",
    },
    {
        "name": "Autopilot",
        "url": "https://learn.microsoft.com/en-us/autopilot/whats-new",
        "cadence": "monthly",
        "category": "Devices",
        "rss": None,
        "selector": "h2, h3, p",
    },
    # Viva What's New — /viva/whats-new resolves but returns 0 parseable items (JS-rendered).
    # No reliable static known-issues page found. Re-enable when a scrapable URL is confirmed.
    # {
    #     "name": "Viva",
    #     "url": "TODO",
    #     "cadence": "monthly",
    #     "category": "Apps",
    #     "rss": None,
    #     "selector": "h2, h3, p",
    # },
    {
        "name": "Global Secure Access",
        # No dedicated "What's New" page exists; using the Windows client release history
        # which publishes versioned release notes per build.
        "url": "https://learn.microsoft.com/en-us/entra/global-secure-access/reference-windows-client-release-history",
        "cadence": "monthly",
        "category": "Network",
        "rss": None,
        "selector": "h2, h3, p",
    },
    # ── Service Health & Known Issues ──────────────────────────────────────────
    # health=True sources are routed to site/data/health.json, not the weekly draft
    {
        "name": "Intune Known Issues",
        "url": "https://learn.microsoft.com/en-us/troubleshoot/mem/intune/known-issues",
        "cadence": "rolling",
        "category": "Service Health & Known Issues",
        "rss": None,
        "selector": "h2, h3, p",
        "health": True,
    },
    {
        "name": "Windows 365 Known Issues",
        "url": "https://learn.microsoft.com/en-us/troubleshoot/windows-365/known-issues-enterprise",
        "cadence": "rolling",
        "category": "Service Health & Known Issues",
        "rss": None,
        "selector": "h2, h3, p",
        "health": True,
    },
    {
        "name": "Autopilot Known Issues",
        "url": "https://learn.microsoft.com/en-us/autopilot/known-issues",
        "cadence": "rolling",
        "category": "Service Health & Known Issues",
        "rss": None,
        "selector": "h2, h3, p",
        "health": True,
    },
    # Autopatch Known Issues — URL needs verification; disabled until confirmed
    # {
    #     "name": "Autopatch Known Issues",
    #     "url": "TODO",
    #     "cadence": "rolling",
    #     "category": "Service Health & Known Issues",
    #     "rss": None,
    #     "selector": "h2, h3, p",
    #     "health": True,
    # },
    {
        "name": "Defender for Endpoint Known Issues",
        "url": "https://learn.microsoft.com/en-us/defender-endpoint/troubleshoot-microsoft-defender-antivirus",
        "cadence": "rolling",
        "category": "Service Health & Known Issues",
        "rss": None,
        "selector": "h2, h3, p",
        "health": True,
    },
    # Defender for Office 365 Known Issues — no dedicated known-issues page found;
    # /defender-office-365/known-issues returns 404. Re-enable if Microsoft publishes one.
    # {
    #     "name": "Defender for Office 365 Known Issues",
    #     "url": "TODO",
    #     "cadence": "rolling",
    #     "category": "Service Health & Known Issues",
    #     "rss": None,
    #     "selector": "h2, h3, p",
    #     "health": True,
    # },
    {
        "name": "Defender XDR Known Issues",
        "url": "https://learn.microsoft.com/en-us/defender-xdr/troubleshoot",
        "cadence": "rolling",
        "category": "Service Health & Known Issues",
        "rss": None,
        "selector": "h2, h3, p",
        "health": True,
    },
    {
        "name": "Purview Known Issues",
        "url": "https://learn.microsoft.com/en-us/purview/data-governance-known-issues",
        "cadence": "rolling",
        "category": "Service Health & Known Issues",
        "rss": None,
        "selector": "h2, h3, p",
        "health": True,
    },
    {
        "name": "Entra ID Known Issues",
        "url": "https://learn.microsoft.com/en-us/entra/identity/app-provisioning/known-issues",
        "cadence": "rolling",
        "category": "Service Health & Known Issues",
        "rss": None,
        "selector": "h2, h3, p",
        "health": True,
    },
    {
        "name": "Teams Known Issues",
        "url": "https://learn.microsoft.com/en-us/microsoftteams/known-issues",
        "cadence": "rolling",
        "category": "Service Health & Known Issues",
        "rss": None,
        "selector": "h2, h3, p",
        "health": True,
    },
    # SharePoint Known Issues — /sharepoint/troubleshoot/known-issues-sharepoint-online-suite 404s.
    # Candidate URL (needs manual verification): https://learn.microsoft.com/en-us/troubleshoot/sharepoint/
    # {
    #     "name": "SharePoint Known Issues",
    #     "url": "TODO",
    #     "cadence": "rolling",
    #     "category": "Service Health & Known Issues",
    #     "rss": None,
    #     "selector": "h2, h3, p",
    #     "health": True,
    # },
    # OneDrive Known Issues — /sharepoint/troubleshoot/onedrive-errors/onedrive-known-issues 404s.
    # No dedicated known-issues page found. Re-enable if Microsoft publishes one.
    # {
    #     "name": "OneDrive Known Issues",
    #     "url": "TODO",
    #     "cadence": "rolling",
    #     "category": "Service Health & Known Issues",
    #     "rss": None,
    #     "selector": "h2, h3, p",
    #     "health": True,
    # },
    # Exchange Known Issues — /exchange/troubleshoot/known-issues/exchange-online-known-issues 404s.
    # Candidate URL (needs manual verification): https://learn.microsoft.com/en-us/troubleshoot/exchange/exchange-online-welcome
    # {
    #     "name": "Exchange Known Issues",
    #     "url": "TODO",
    #     "cadence": "rolling",
    #     "category": "Service Health & Known Issues",
    #     "rss": None,
    #     "selector": "h2, h3, p",
    #     "health": True,
    # },
    # Viva Known Issues — /viva/known-issues 404s.
    # Candidate URL (needs manual verification): https://learn.microsoft.com/en-us/troubleshoot/viva/
    # {
    #     "name": "Viva Known Issues",
    #     "url": "TODO",
    #     "cadence": "rolling",
    #     "category": "Service Health & Known Issues",
    #     "rss": None,
    #     "selector": "h2, h3, p",
    #     "health": True,
    # },
    {
        "name": "Windows Release Health",
        "url": "https://learn.microsoft.com/en-us/windows/release-health/",
        "cadence": "rolling",
        "category": "Service Health & Known Issues",
        "rss": None,
        "selector": "h2, h3, p",
        "health": True,
    },
]

# Classification keywords — Zero Trust pillar alignment
# Pillars: Identity, Devices, Apps, Data, Network, Visibility & Automation
CLASSIFICATION_KEYWORDS = {
    "Identity": [
        "entra", "azure ad", "conditional access", "mfa", "passwordless",
        "passkey", "sso", "saml", "oauth", "identity", "authentication",
        "hard-match", "cloud sync", "connect sync", "privileged", "pim",
        "lifecycle workflows", "external mfa", "certificate-based", "cba",
        "entitlement management", "access review", "identity governance",
    ],
    "Devices": [
        "intune", "autopatch", "mdm", "enrollment", "compliance policy",
        "configuration profile", "remediation", "hotpatch", "windows update",
        "endpoint", "device management", "managed device", "linux", "macos",
        "android enterprise", "apple", "tvos", "visionos", "epm",
        "endpoint privilege", "laps", "firmware",
    ],
    "Apps": [
        "teams", "sharepoint", "onedrive", "outlook", "copilot", "calendar",
        "meeting", "channel", "viva", "loop", "planner", "yammer",
        "forms", "power apps", "microsoft 365 apps", "office", "ai charts",
    ],
    "Data": [
        "purview", "dlp", "sensitivity label", "insider risk", "dspm",
        "information protection", "data loss", "data governance",
        "compliance", "retention", "ediscovery", "communications compliance",
        "records management", "data lifecycle",
    ],
    "Network": [
        "global secure access", "network", "vpn", "firewall", "ztna",
        "remote network", "traffic forwarding", "private access",
        "internet access", "cloud firewall", "network segmentation",
    ],
    "Visibility & Automation": [
        "defender", "sentinel", "attack disruption", "predictive shielding",
        "secure score", "vulnerability", "threat", "incident", "hunting",
        "xdr", "siem", "soar", "graph api", "powershell", "rest api",
        "automation", "agent", "copilot studio", "agent 365", "shadow ai",
        "ai gateway", "prompt injection", "llm", "generative ai", "logic app",
        "workflow", "api", "sdk", "webhook", "power automate", "power platform",
    ],
}

# Rollout phase keywords
PHASE_KEYWORDS = {
    "Preview": ["preview", "public preview", "private preview", "beta", "in development"],
    "GA": ["generally available", "now available", "ga", "released"],
    "Targeted": ["targeted release", "targeted rollout", "first release"],
    "Broad": ["broad deployment", "full rollout", "all tenants", "worldwide"],
}
