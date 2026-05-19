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
    # SharePoint / OneDrive — disabled, URL keeps changing on Microsoft's end
    # Re-enable when a stable what's-new URL is found
    # {
    #     "name": "SharePoint / OneDrive",
    #     "url": "https://learn.microsoft.com/en-us/SharePoint/what-s-new-in-sharepoint",
    #     "cadence": "rolling",
    #     "category": "Collaboration & Productivity",
    #     "rss": None,
    #     "selector": "h2, h3, p",
    # },
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
        "name": "Defender XDR Service Issues",
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
]

# Classification keywords — used to override default source category
CLASSIFICATION_KEYWORDS = {
    "Endpoint Management": [
        "intune", "autopatch", "mdm", "enrollment", "compliance policy",
        "configuration profile", "remediation", "hotpatch", "windows update",
        "lxc", "endpoint", "device management", "managed device", "linux", "macos",
        "android enterprise", "apple", "tvos", "visionos",
    ],
    "Identity & Access": [
        "entra", "azure ad", "conditional access", "mfa", "passwordless",
        "passkey", "sso", "saml", "oauth", "identity", "authentication",
        "hard-match", "cloud sync", "connect sync", "privileged", "pim",
        "lifecycle workflows", "external mfa", "global secure access",
    ],
    "Security & Compliance": [
        "defender", "purview", "dlp", "sentinel", "attack disruption",
        "predictive shielding", "secure score", "vulnerability", "threat",
        "incident", "hunting", "xdr", "siem", "dspm", "insider risk",
        "information protection", "data loss", "compliance", "secure boot",
    ],
    "Collaboration & Productivity": [
        "teams", "sharepoint", "onedrive", "outlook", "copilot", "calendar",
        "meeting", "channel", "viva", "loop", "planner", "yammer",
        "forms", "power automate", "power apps", "ai charts",
    ],
    "Automation & AI": [
        "graph api", "powershell", "rest api", "automation", "agent",
        "copilot studio", "agent 365", "shadow ai", "ai gateway",
        "prompt injection", "llm", "generative ai", "logic app", "workflow",
        "api", "sdk", "webhook", "power automate",
    ],
}

# Rollout phase keywords
PHASE_KEYWORDS = {
    "Preview": ["preview", "public preview", "private preview", "beta", "in development"],
    "GA": ["generally available", "now available", "ga", "released"],
    "Targeted": ["targeted release", "targeted rollout", "first release"],
    "Broad": ["broad deployment", "full rollout", "all tenants", "worldwide"],
}
