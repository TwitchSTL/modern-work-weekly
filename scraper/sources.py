"""
sources.py — Microsoft portal source definitions for the scraper.

Each source has:
  - name: display name (also used as the "source" field on scraped items,
    the item_id hash input, and the name shown in Exec Guide citations)
  - url: the "What's New" or release notes page
  - cadence: how often it updates
  - rss: RSS feed URL if available (preferred over HTML scraping)
  - selector: CSS selector for HTML fallback (if no RSS)
  - health: True if this is a known-issues/service-health source (routed separately)
  - json_api: True if the rss field is a JSON endpoint (not RSS/Atom) — uses fetch_json_status()
  - no_item_dates: True if this feed has no real per-item publish date (see
    Microsoft 365 Roadmap below) — tells fetch_rss() to record date=None
    instead of faking "now"

Note: sources used to carry a "category" field ("default classification
bucket"). It was removed 2026-07-17 — it was never actually read anywhere;
classify_item() in scraper.py always classifies from the item's title/body
text against CLASSIFICATION_KEYWORDS below, regardless of which source it
came from. The field had drifted into a stale mix of old and new taxonomy
labels across different sources, which was confusing to read and implied a
behavior it didn't have. If you want a source's likely pillar for reference,
see the README's "Sources scraped" table instead — that's curated by hand
and isn't tied to any code path.

Last reviewed: 2026-07-17
Changes from prior version:
  - Removed the unused per-source "category" field (see note above)
  - Renamed "Microsoft Security Blog (Zero Trust)" to "Microsoft Security
    Blog" — the parenthetical was left over from the old Zero Trust pillar
    taxonomy and no longer reflects how the site is organized
Changes from 2026-06-01 version:
  - Teams: switched from /officeupdates/teams-admin (per-build admin changelog) to
    TechCommunity Teams blog, which publishes monthly "What's New" feature digests
  - SharePoint / OneDrive: switched from support.microsoft.com consumer article to
    learn.microsoft.com admin-oriented page (static, scrapable)
  - Global Secure Access: switched from Windows client release history to the service
    what's-new page (/entra/global-secure-access/whats-new)
  - Defender for Endpoint: URL slug verified — old slug is the LIVE page;
    /whats-new-mde is the archive. No change made.
  - Added rss= entries for 13 sources that previously had rss=None
  - Added Windows Autopatch (was TODO with blank URL)
  - Added Defender for Identity (separate what's-new page from Defender XDR)
  - Added Azure Status and M365 Service Status as public health sources
  - Updated comments on scoped known-issues pages (Purview, Entra, MDE)
"""

SOURCES = [
    # ── Release & Feature Update Sources ──────────────────────────────────────
    {
        "name": "Intune",
        "url": "https://learn.microsoft.com/en-us/intune/intune-service/fundamentals/whats-new",
        "cadence": "weekly",
        "rss": "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=microsoftintuneblog",
        "selector": "h2, h3, p",
    },
    {
        "name": "Defender XDR",
        "url": "https://learn.microsoft.com/en-us/defender-xdr/whats-new",
        "cadence": "monthly",
        "rss": "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=microsoft-security-blog",
        "selector": "h2, h3, p",
    },
    {
        "name": "Entra ID",
        "url": "https://learn.microsoft.com/en-us/entra/fundamentals/whats-new",
        "cadence": "monthly",
        "rss": "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=microsoft-entra-blog",
        "selector": "h2, h3, p",
    },
    {
        "name": "Teams",
        # Switched from /officeupdates/teams-admin (per-build admin changelog) to the
        # TechCommunity Teams blog, which publishes monthly "What's New in Microsoft Teams"
        # feature digests — the right content level for a weekly digest.
        # Per-build release notes remain at: learn.microsoft.com/en-us/officeupdates/teams-admin
        "url": "https://techcommunity.microsoft.com/t5/microsoft-teams-blog/bg-p/MicrosoftTeamsBlog",
        "cadence": "monthly",
        "rss": "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=microsoftteamsblog",
        "selector": "h2, h3, p",
    },
    {
        "name": "Microsoft Security Blog",
        "url": "https://www.microsoft.com/en-us/security/blog/",
        "cadence": "rolling",
        "rss": "https://www.microsoft.com/en-us/security/blog/feed/",
        "selector": None,
    },
    {
        "name": "Purview",
        "url": "https://learn.microsoft.com/en-us/purview/whats-new",
        "cadence": "monthly",
        "rss": "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=microsoft-purview-blog",
        "selector": "h2, h3, p",
    },
    {
        "name": "SharePoint / OneDrive",
        # Switched from support.microsoft.com consumer article (JS-heavy, not scrapable)
        # to the learn.microsoft.com admin-oriented page — static, consistently structured,
        # and aligned with the rest of the SOURCES entries.
        "url": "https://learn.microsoft.com/en-us/sharepoint/what-s-new-in-sharepoint",
        "cadence": "rolling",
        "rss": "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=SPBlog",
        "selector": "h2, h3, p",
    },
    {
        "name": "Microsoft 365 Roadmap",
        "url": "https://www.microsoft.com/en-us/microsoft-365/roadmap",
        "cadence": "rolling",
        "rss": "https://www.microsoft.com/en-us/microsoft-365/RoadmapFeatureRSS",
        "selector": None,
        # Confirmed 2026-07-17: this feed has no per-entry publish date — every
        # item comes back stamped with the scrape time itself, which made the
        # freshness filter think every item was brand new regardless of true
        # age. no_item_dates tells fetch_rss() to record date=None instead of
        # faking "now", so age-based filtering correctly treats these items as
        # unknown-age (kept, never wrongly aged out) rather than falsely fresh.
        "no_item_dates": True,
    },
    {
        "name": "Agent 365",
        # Using /category/ URL as no legacy /t5/ path was confirmed for this blog.
        # RSS falls back to M365 blog feed — no dedicated Agent 365 RSS confirmed yet.
        "url": "https://techcommunity.microsoft.com/category/microsoft365/blog/agent-365-blog",
        "cadence": "monthly",
        "rss": "https://www.microsoft.com/en-us/microsoft-365/blog/feed/",
        "selector": "h2, h3, p",
    },
    {
        "name": "Defender for Endpoint",
        # URL slug verified: /whats-new-in-microsoft-defender-endpoint is the LIVE page
        # (active content as of Dec 2025). /whats-new-mde is the ARCHIVE. No change.
        "url": "https://learn.microsoft.com/en-us/defender-endpoint/whats-new-in-microsoft-defender-endpoint",
        "cadence": "monthly",
        "rss": "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=microsoft-security-blog",
        "selector": "h2, h3, p",
    },
    {
        "name": "Defender for Identity",
        # Has its own what's-new page separate from the Defender XDR rollup page.
        # Actively updated — confirmed May 2026 content.
        "url": "https://learn.microsoft.com/en-us/defender-for-identity/whats-new",
        "cadence": "monthly",
        "rss": "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=microsoft-security-blog",
        "selector": "h2, h3, p",
    },
    {
        "name": "Defender for Office 365",
        "url": "https://learn.microsoft.com/en-us/defender-office-365/defender-for-office-365-whats-new",
        "cadence": "monthly",
        "rss": "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=microsoft-security-blog",
        "selector": "h2, h3, p",
    },
    {
        "name": "Exchange Online",
        "url": "https://learn.microsoft.com/en-us/exchange/whats-new",
        "cadence": "monthly",
        "rss": "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=exchange",
        "selector": "h2, h3, p",
    },
    {
        "name": "Windows 365",
        "url": "https://learn.microsoft.com/en-us/windows-365/whats-new",
        "cadence": "monthly",
        "rss": "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=windows-itpro-blog",
        "selector": "h2, h3, p",
    },
    {
        "name": "Windows Autopatch",
        # No year-specific what's-new page exists for Autopatch.
        # Microsoft publishes monthly "Windows news you can use" posts on the Windows IT Pro
        # blog that serve as the canonical Autopatch update digest.
        "url": "https://techcommunity.microsoft.com/t5/windows-it-pro-blog/bg-p/Windows10Blog",
        "cadence": "monthly",
        "rss": "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=windows-itpro-blog",
        "selector": "h2, h3, p",
    },
    {
        "name": "Autopilot",
        "url": "https://learn.microsoft.com/en-us/autopilot/whats-new",
        "cadence": "monthly",
        "rss": "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=microsoftintuneblog",
        "selector": "h2, h3, p",
    },
    {
        "name": "Microsoft 365 Copilot",
        # Monthly "What's New in Microsoft 365 Copilot" posts — the primary Copilot
        # feature update signal for Modern Work engineers.
        # Blog: techcommunity.microsoft.com/category/microsoft365copilot/blog/microsoft365copilotblog
        "url": "https://techcommunity.microsoft.com/category/microsoft365copilot/blog/microsoft365copilotblog",
        "cadence": "monthly",
        "rss": "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=Microsoft365CopilotBlog",
        "selector": "h2, h3, p",
    },
    {
        "name": "Copilot Studio",
        # TechCommunity blog for Copilot Studio (formerly Power Virtual Agents) —
        # covers agent-building, connectors, and platform updates.
        # Blog: techcommunity.microsoft.com/category/microsoft365copilot/blog/copilot-studio-blog
        "url": "https://techcommunity.microsoft.com/category/microsoft365copilot/blog/copilot-studio-blog",
        "cadence": "monthly",
        "rss": "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=copilot-studio-blog",
        "selector": "h2, h3, p",
    },
    {
        "name": "Power Platform",
        # Microsoft Power Platform blog — Power Automate, Power Apps, Power BI updates
        # relevant to Modern Work automation. Hosted at powerplatform.microsoft.com.
        "url": "https://powerplatform.microsoft.com/en-us/blog/",
        "cadence": "monthly",
        "rss": "https://powerplatform.microsoft.com/en-us/blog/feed/",
        "selector": None,
    },
    {
        "name": "Microsoft Viva",
        # TechCommunity blog covering Viva Insights, Viva Learning, Viva Engage,
        # and the broader Viva suite — monthly cadence.
        # Blog: techcommunity.microsoft.com/category/microsoft-viva/blog/microsoftvivablog
        "url": "https://techcommunity.microsoft.com/category/microsoft-viva/blog/microsoftvivablog",
        "cadence": "monthly",
        "rss": "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=MicrosoftVivaBlog",
        "selector": "h2, h3, p",
    },
    {
        "name": "Microsoft Security Response Center",
        # MSRC publishes CVE advisories and patch guidance for Windows, Edge, and
        # M365 apps. High-signal source for security-conscious Modern Work engineers.
        "url": "https://msrc.microsoft.com/update-guide/",
        "cadence": "rolling",
        "rss": "https://api.msrc.microsoft.com/update-guide/rss",
        "selector": None,
    },
    {
        "name": "Microsoft Mechanics",
        # Microsoft's official technical how-to YouTube channel — step-by-step videos
        # on deploying and configuring M365 services. YouTube Atom feed via feedparser.
        "url": "https://www.youtube.com/@MicrosoftMechanics",
        "cadence": "rolling",
        "rss": "https://www.youtube.com/feeds/videos.xml?channel_id=UCnUYZLuoy1rq1aVMwx4aTzw",
        "selector": None,
    },
    {
        "name": "Global Secure Access",
        # Switched from Windows client release history (version numbers only) to the
        # service-level what's-new page, which covers feature announcements and updates.
        # Client version tracking (if needed): /entra/global-secure-access/reference-windows-client-release-history
        "url": "https://learn.microsoft.com/en-us/entra/global-secure-access/whats-new",
        "cadence": "monthly",
        "rss": "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=microsoft-entra-blog",
        "selector": "h2, h3, p",
    },

    # ── Service Health & Known Issues ──────────────────────────────────────────
    # health=True sources are routed to site/data/health.json, not the weekly draft
    {
        "name": "Intune Known Issues",
        "url": "https://learn.microsoft.com/en-us/troubleshoot/mem/intune/known-issues",
        "cadence": "rolling",
        "rss": None,
        "selector": "h2, h3, p",
        "health": True,
    },
    {
        "name": "Windows 365 Known Issues",
        "url": "https://learn.microsoft.com/en-us/troubleshoot/windows-365/known-issues-enterprise",
        "cadence": "rolling",
        "rss": None,
        "selector": "h2, h3, p",
        "health": True,
    },
    {
        "name": "Autopilot Known Issues",
        "url": "https://learn.microsoft.com/en-us/autopilot/known-issues",
        "cadence": "rolling",
        "rss": None,
        "selector": "h2, h3, p",
        "health": True,
    },
    # Autopatch Known Issues — no dedicated known-issues page confirmed.
    # Windows Release Health (below) covers Autopatch-related issues inline.
    # {
    #     "name": "Autopatch Known Issues",
    #     "url": "TODO",
    #     "cadence": "rolling",
    #     "rss": None,
    #     "selector": "h2, h3, p",
    #     "health": True,
    # },
    # Defender for Endpoint Known Issues — removed. The troubleshoot-microsoft-defender-antivirus
    # page is an event log reference (bare numeric event IDs as headings), not a known issues
    # tracker. No MDE-wide known-issues page exists. Re-enable if Microsoft publishes one.
    # {
    #     "name": "Defender for Endpoint Known Issues",
    #     "url": "https://learn.microsoft.com/en-us/defender-endpoint/troubleshoot-microsoft-defender-antivirus",
    #     "cadence": "rolling",
    #     "rss": None,
    #     "selector": "h2, h3, p",
    #     "health": True,
    # },
    # Defender for Office 365 Known Issues — no dedicated known-issues page confirmed.
    # Re-enable if Microsoft publishes one.
    # {
    #     "name": "Defender for Office 365 Known Issues",
    #     "url": "TODO",
    #     "cadence": "rolling",
    #     "rss": None,
    #     "selector": "h2, h3, p",
    #     "health": True,
    # },
    {
        "name": "Defender XDR Known Issues",
        "url": "https://learn.microsoft.com/en-us/defender-xdr/troubleshoot",
        "cadence": "rolling",
        "rss": None,
        "selector": "h2, h3, p",
        "health": True,
    },
    {
        "name": "Purview Known Issues",
        # Scoped to data governance — does not cover DLP, IRM, or communication compliance.
        # No broader /purview/known-issues page was confirmed. Update URL if Microsoft
        # publishes a wider-scoped known-issues page.
        "url": "https://learn.microsoft.com/en-us/purview/data-governance-known-issues",
        "cadence": "rolling",
        "rss": None,
        "selector": "h2, h3, p",
        "health": True,
    },
    {
        "name": "Entra ID Known Issues",
        # Scoped to app provisioning — no single Entra-wide known-issues page exists.
        # The what's-new page (/entra/fundamentals/whats-new) includes deprecation and
        # breaking-change notices, which partially fills the gap.
        "url": "https://learn.microsoft.com/en-us/entra/identity/app-provisioning/known-issues",
        "cadence": "rolling",
        "rss": None,
        "selector": "h2, h3, p",
        "health": True,
    },
    # Teams Known Issues — removed. The page's heading structure results in
    # duplicate URLs across items (all pointing to the same anchor), making
    # the sidebar entries redundant and unhelpful.
    # {
    #     "name": "Teams Known Issues",
    #     "url": "https://learn.microsoft.com/en-us/microsoftteams/known-issues",
    #     "cadence": "rolling",
    #     "rss": None,
    #     "selector": "h2, h3, p",
    #     "health": True,
    # },
    # SharePoint Known Issues — candidate URL needs manual validation before enabling:
    # https://learn.microsoft.com/en-us/troubleshoot/sharepoint/
    # {
    #     "name": "SharePoint Known Issues",
    #     "url": "TODO",
    #     "cadence": "rolling",
    #     "rss": None,
    #     "selector": "h2, h3, p",
    #     "health": True,
    # },
    # OneDrive Known Issues — no dedicated page confirmed.
    # Best proxy is the SharePoint troubleshoot index above.
    # {
    #     "name": "OneDrive Known Issues",
    #     "url": "TODO",
    #     "cadence": "rolling",
    #     "rss": None,
    #     "selector": "h2, h3, p",
    #     "health": True,
    # },
    # Exchange Known Issues — candidate URL needs manual validation before enabling:
    # https://learn.microsoft.com/en-us/troubleshoot/exchange/exchange-online-welcome
    # {
    #     "name": "Exchange Known Issues",
    #     "url": "TODO",
    #     "cadence": "rolling",
    #     "rss": None,
    #     "selector": "h2, h3, p",
    #     "health": True,
    # },
    # Viva Known Issues — candidate URL needs manual validation before enabling:
    # https://learn.microsoft.com/en-us/troubleshoot/viva/
    # {
    #     "name": "Viva Known Issues",
    #     "url": "TODO",
    #     "cadence": "rolling",
    #     "rss": None,
    #     "selector": "h2, h3, p",
    #     "health": True,
    # },
    {
        "name": "Windows Release Health",
        "url": "https://learn.microsoft.com/en-us/windows/release-health/",
        "cadence": "rolling",
        "rss": None,
        "selector": "h2, h3, p",
        "health": True,
    },
    {
        "name": "Azure Status",
        # Public Atom feed, no auth required. Covers Azure infrastructure incidents that
        # can affect M365-dependent services (Exchange Online, Teams, SharePoint).
        "url": "https://status.azure.com",
        "cadence": "rolling",
        "rss": "https://azurestatuscdn.azureedge.net/en-us/status/feed/",
        "selector": None,
        "health": True,
    },
    {
        "name": "Microsoft 365 Service Status",
        # Public JSON endpoint, no auth required. Returns a messages array.
        # json_api=True routes this to fetch_json_status() instead of feedparser.
        # If Graph API access is added later, Message Center replaces this entirely.
        "url": "https://status.office365.com",
        "cadence": "rolling",
        "rss": "https://status.office365.com/api/messages",
        "selector": None,
        "health": True,
        "json_api": True,
    },
]

# Classification keywords — Modern Work practice-area alignment
# Pillars: Identity & Access, Endpoint & Device Management, Collaboration &
# Productivity, AI & Copilot, Employee Experience, Security & Compliance
#
# Reframed 2026-07 from the prior Zero Trust security-pillar taxonomy
# (Identity, Devices, Apps, Data, Network, Visibility & Automation) so the
# site's categories reflect Modern Work practice areas rather than a purely
# security lens. Every keyword from the old taxonomy was preserved and
# redistributed below — nothing was dropped, only regrouped — plus new
# Employee Experience terms since "viva"/"yammer" alone weren't enough
# surface area for that pillar to reliably trigger. Historical posts (through
# 2026-07-14) keep their original Zero Trust category labels; this taxonomy
# applies starting with the next digest (forward-only, no retroactive
# relabeling — avoids breaking links into already-published category
# sections).
CLASSIFICATION_KEYWORDS = {
    "Identity & Access": [
        # unchanged from prior "Identity"
        "entra", "azure ad", "conditional access", "mfa", "passwordless",
        "passkey", "sso", "saml", "oauth", "identity", "authentication",
        "hard-match", "cloud sync", "connect sync", "privileged", "pim",
        "lifecycle workflows", "external mfa", "certificate-based", "cba",
        "entitlement management", "access review", "identity governance",
    ],
    "Endpoint & Device Management": [
        # unchanged from prior "Devices"
        "intune", "autopatch", "mdm", "enrollment", "compliance policy",
        "configuration profile", "remediation", "hotpatch", "windows update",
        "endpoint", "device management", "managed device", "linux", "macos",
        "android enterprise", "apple", "tvos", "visionos", "epm",
        "endpoint privilege", "laps", "firmware",
    ],
    "Collaboration & Productivity": [
        # from prior "Apps", minus copilot/viva/yammer/power apps (moved below)
        "teams", "sharepoint", "onedrive", "outlook", "calendar",
        "meeting", "channel", "loop", "planner", "forms",
        "microsoft 365 apps", "office",
    ],
    "AI & Copilot": [
        # copilot/ai charts/power apps from prior "Apps" + the AI/agent/Power
        # Platform terms from prior "Visibility & Automation"
        "copilot", "ai charts", "power apps", "copilot studio", "agent 365",
        "shadow ai", "ai gateway", "prompt injection", "llm", "generative ai",
        "power automate", "power platform",
    ],
    "Employee Experience": [
        # viva/yammer moved from prior "Apps"; rest are new additions
        "viva", "yammer", "viva engage", "viva insights", "viva learning",
        "viva goals", "employee experience", "engagement", "wellbeing",
        "workplace analytics", "worklab",
    ],
    "Security & Compliance": [
        # prior "Data" + "Network" + the security-ops portion of prior
        # "Visibility & Automation" (everything except AI/agent terms, which
        # moved to "AI & Copilot" above)
        "purview", "dlp", "sensitivity label", "insider risk", "dspm",
        "information protection", "data loss", "data governance",
        "compliance", "retention", "ediscovery", "communications compliance",
        "records management", "data lifecycle",
        "global secure access", "gsa", "network", "vpn", "firewall", "ztna",
        "remote network", "traffic forwarding", "private access",
        "internet access", "cloud firewall", "network segmentation",
        "defender", "sentinel", "attack disruption", "predictive shielding",
        "secure score", "vulnerability", "threat", "incident", "hunting",
        "secure boot", "security baseline",
        "xdr", "siem", "soar", "graph api", "powershell", "rest api",
        "automation", "logic app", "workflow", "api", "sdk", "webhook",
    ],
}

# Fallback category for an item that scores zero keyword hits across every
# pillar above. Kept security-leaning on purpose — better to have an
# unrecognized item surface under Security & Compliance for a human to
# reclassify than have it silently disappear into a busy, unrelated pillar.
# See classify_item() in scraper.py: it now reports whether an item's
# category came from a real keyword match or this fallback, and
# write_classification_stats() tracks the fallback rate per run so a rising
# trend is visible instead of discovered by accident.
DEFAULT_CATEGORY = "Security & Compliance"

# Rollout phase keywords
PHASE_KEYWORDS = {
    "Preview": ["preview", "public preview", "private preview", "beta", "in development"],
    "GA": ["generally available", "now available", "ga", "released"],
    "Targeted": ["targeted release", "targeted rollout", "first release"],
    "Broad": ["broad deployment", "full rollout", "all tenants", "worldwide"],
}
