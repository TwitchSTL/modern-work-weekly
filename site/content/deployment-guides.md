---
title: "Deployment Guides"
date: 2026-08-29
lastmod: 2026-08-29
description: "Official Microsoft deployment and setup guides for Intune, Defender, Entra, Copilot, Purview, and Viva, organized by Modern Work practice area, plus what actually changes across Commercial, GCC, GCC High, and DoD."
draft: false
pillar_page: true
categories:
  - Identity & Access
  - Endpoint & Device Management
  - Collaboration & Productivity
  - AI & Copilot
  - Employee Experience
  - Security & Compliance
tags:
  - intune
  - endpoint-management
  - entra-id
  - identity
  - conditional-access
  - teams
  - sharepoint
  - onedrive
  - exchange
  - copilot
  - viva
  - defender-xdr
  - defender-for-endpoint
  - defender-for-office-365
  - defender-for-identity
  - purview
  - zero-trust
  - windows-365
  - security
  - modern-work
faq:
  - q: "Are these Microsoft's own guides, or written by Modern Work Weekly?"
    a: "Every link on this page goes to an official Microsoft resource: Microsoft Learn documentation or a Microsoft 365 Setup Portal guide. This page doesn't rewrite Microsoft's guidance, it organizes it by Modern Work practice area so you don't have to hunt across learn.microsoft.com and the admin center to find the right starting point."
  - q: "Do I need to sign in to use these guides?"
    a: "The Microsoft Learn documentation links work for anyone. The Microsoft 365 Setup Portal guides (the ones with step-by-step checklists) are also publicly viewable without signing in, though a few advanced guides are admin-center-only and require signing in to a tenant with an appropriate admin role, most commonly Global Reader to view or Global Administrator to make changes."
  - q: "What's the difference between GCC, GCC High, and DoD?"
    a: "All three are Microsoft's U.S. government cloud environments, ordered by isolation level. GCC is for federal, state, and local agencies and contractors needing U.S. data residency and FedRAMP Moderate alignment. GCC High adds isolation for organizations handling Controlled Unclassified Information (CUI) and DFARS or ITAR requirements. DoD is the most restricted, built exclusively for the Department of Defense. Feature availability lags behind commercial in that order too, so check a workload's availability before you plan around it."
  - q: "Can I use these advanced deployment guides in GCC High or DoD?"
    a: "No. Microsoft's advanced deployment guides in the admin center and Setup Portal are not available in GCC High, DoD, or Microsoft 365 operated by 21Vianet. If you're in one of those environments, go directly to the Microsoft Learn documentation for the product instead, and confirm feature parity for your environment before you plan a rollout around it."
pillars:
  - name: "Identity & Access"
    color: "identity-access"
    guides:
      - title: "Microsoft Entra deployment plans"
        url: "https://learn.microsoft.com/entra/architecture/deployment-plans"
        desc: "The hub for authentication, hybrid identity, governance, and app-management deployment plans."
      - title: "Microsoft Entra setup guide"
        url: "https://go.microsoft.com/fwlink/?linkid=2223229"
        desc: "Hybrid sync, self-service password reset, Conditional Access, and third-party SSO, in one guided checklist."
      - title: "Plan a Conditional Access deployment"
        url: "https://learn.microsoft.com/entra/identity/conditional-access/plan-conditional-access"
        desc: "How to design and roll out Conditional Access policies without locking yourself out."
      - title: "Plan a Microsoft Entra multifactor authentication deployment"
        url: "https://learn.microsoft.com/entra/identity/authentication/howto-mfa-getstarted"
        desc: "Prerequisites, authentication methods, and a pilot-then-expand rollout plan for MFA."
      - title: "Plan a passwordless authentication deployment in Microsoft Entra ID"
        url: "https://learn.microsoft.com/entra/identity/authentication/howto-authentication-passwordless-deployment"
        desc: "Windows Hello for Business, Authenticator, and FIDO2 security keys as password replacements."
  - name: "Endpoint & Device Management"
    color: "endpoint-device"
    guides:
      - title: "Deploy and set up Microsoft Intune and Intune Suite"
        url: "https://go.microsoft.com/fwlink/?linkid=2223058"
        desc: "MDM and MAM setup, compliance and app protection policies, and Intune Suite features."
      - title: "Windows device enrollment guide for Microsoft Intune"
        url: "https://learn.microsoft.com/intune/device-enrollment/windows/guide"
        desc: "Choosing the right enrollment method: Autopilot, hybrid join, Group Policy, or bulk provisioning."
      - title: "Deployment guide: Manage devices running Windows"
        url: "https://learn.microsoft.com/intune/fundamentals/platform-guide-windows"
        desc: "Prerequisites through enrollment for Windows endpoints specifically, task by task."
      - title: "Windows 365 Enterprise deployment checklist"
        url: "https://go.microsoft.com/fwlink/?linkid=2240015"
        desc: "Cloud PC provisioning: Entra-joined vs. hybrid networking, image configuration, and health checks."
  - name: "Collaboration & Productivity"
    color: "collaboration-productivity"
    guides:
      - title: "Microsoft Teams setup guide"
        url: "https://go.microsoft.com/fwlink/?linkid=2222975"
        desc: "Guest access, team-creation permissions, and network requirements for a Teams rollout."
      - title: "Plan and implement your Microsoft Teams Phone deployment"
        url: "https://go.microsoft.com/fwlink/?linkid=2223356"
        desc: "Calling Plans, Operator Connect, Teams Phone Mobile, and Direct Routing, compared side by side."
      - title: "SharePoint setup guide"
        url: "https://go.microsoft.com/fwlink/?linkid=2223320"
        desc: "Sharing permission policies, migration tooling, and site security settings."
      - title: "OneDrive setup guide"
        url: "https://go.microsoft.com/fwlink/?linkid=2223143"
        desc: "Sync client rollout, external sharing controls, and advanced security settings."
      - title: "Microsoft 365 Apps setup guide"
        url: "https://go.microsoft.com/fwlink/?linkid=2234169"
        desc: "Activation, deployment methods, and update channels for Word, Excel, PowerPoint, and OneNote."
  - name: "AI & Copilot"
    color: "ai-copilot"
    guides:
      - title: "Microsoft Copilot setup guide"
        url: "https://go.microsoft.com/fwlink/?linkid=2249661"
        desc: "License assignment, update channels, and the Copilot Control System, start to finish."
      - title: "Secure and governed data foundation for Microsoft Copilot"
        url: "https://learn.microsoft.com/microsoft-365/copilot/secure-govern-copilot-foundational-deployment-guidance"
        desc: "Fixing SharePoint oversharing before rollout using Purview DSPM and sensitivity labels."
      - title: "Deployment overview for the Microsoft Copilot app"
        url: "https://learn.microsoft.com/microsoft-365/copilot/deploy-microsoft-365-copilot-app"
        desc: "How automatic installation with Microsoft 365 Apps works, and how to block it if you're not ready."
  - name: "Employee Experience"
    color: "employee-experience"
    guides:
      - title: "Set up Microsoft Viva"
        url: "https://learn.microsoft.com/viva/setup-microsoft-viva"
        desc: "Per-app setup for Viva Glint, Goals, Insights, Learning, and Pulse."
      - title: "Advanced deployment guides for Microsoft Viva"
        url: "https://learn.microsoft.com/viva/deployment-guides-for-microsoft-viva"
        desc: "Guided setup checklists for Viva Connections, Viva Engage, and Viva Amplify."
      - title: "Getting started with Microsoft Viva"
        url: "https://learn.microsoft.com/viva/getting-started-with-microsoft-viva"
        desc: "Which Viva apps fit which business scenario, before you commit to a deployment plan."
  - name: "Security & Compliance"
    color: "security-compliance"
    guides:
      - title: "Setup guides for Microsoft Defender XDR"
        url: "https://learn.microsoft.com/defender-xdr/deploy-configure-m365-defender"
        desc: "Deployment guides for Defender for Endpoint, Office 365, Identity, and Cloud Apps in one place."
      - title: "Pilot and deploy Microsoft Defender XDR"
        url: "https://learn.microsoft.com/defender-xdr/pilot-deploy-overview"
        desc: "Microsoft's recommended order: Identity, then Office 365, then Endpoint, then Cloud Apps."
      - title: "Unify your security operations"
        url: "https://go.microsoft.com/fwlink/?linkid=2320601"
        desc: "Bringing Microsoft Sentinel and Defender XDR together into one SecOps platform."
      - title: "Microsoft Purview setup guides"
        url: "https://learn.microsoft.com/purview/purview-fast-track-setup-guides"
        desc: "Guided setup for DLP, Information Protection, Data Lifecycle Management, and eDiscovery."
      - title: "Secure by default with Microsoft Purview"
        url: "https://go.microsoft.com/fwlink/?linkid=2310737"
        desc: "Encryption and sensitivity-label defaults that cut down on manual labeling work."
---

{{< quickanswer >}}
Microsoft publishes official, step-by-step deployment guides for nearly every Modern Work service, but they're scattered across Microsoft Learn, the Microsoft 365 Setup Portal, and the admin center. This page organizes the ones worth starting from by practice area, and covers what actually changes if you're deploying into GCC, GCC High, or DoD instead of commercial.
{{< /quickanswer >}}

Every guide below is a Microsoft resource, not something written here. Most are freely viewable; a handful of the more advanced ones live only in the Microsoft 365 admin center and require signing in with an appropriate admin role. Where Microsoft offers both a public Setup Portal version and an admin-center version of the same guide, we've linked whichever is easiest to reach.

## Environments and licensing

Before you start any of the guides below, confirm which Microsoft cloud environment you're actually deploying into. The guidance is broadly the same across environments, but availability, timing, and a few features are not.

**Commercial (worldwide)** is the environment nearly every organization outside the U.S. public sector uses. It gets new features first, and this is what the guides below assume unless noted otherwise.

**GCC (Government Community Cloud)** is for U.S. federal, state, local, and tribal agencies, and contractors handling data subject to U.S. government requirements. It has U.S.-only data residency and aligns with FedRAMP Moderate. Feature releases typically lag commercial.

**GCC High** adds isolation for organizations handling Controlled Unclassified Information (CUI) or subject to DFARS and ITAR requirements, most commonly Defense Industrial Base contractors. Feature availability lags further behind GCC.

**DoD** is the most restricted environment, built exclusively for the U.S. Department of Defense and its mission partners, assessed against DoD Impact Level 5 controls.

One practical consequence for this page specifically: Microsoft's advanced deployment guides, the interactive checklists linked throughout, are **not available in GCC High, DoD, or Microsoft 365 operated by 21Vianet**. If that's your environment, use the Microsoft Learn documentation links instead and verify feature parity before you plan a rollout around any specific capability.

## Deployment guides by practice area
