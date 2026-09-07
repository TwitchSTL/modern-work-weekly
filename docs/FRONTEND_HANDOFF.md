# Modern Work Weekly: Front-End Enhancement Handoff

**Prepared:** 2026-08-08
**Amended:** 2026-08-08 (round 2) — renamed the News Room concept to **News Universe**, resolved several open questions, capped tags at 8-10, and re-sequenced the build order around a content backfill first, News Universe second, everything else low-risk-to-high-risk after that. See §4 (Decisions), §5 (Build order), and §8 (Open questions).
**Site:** https://modernworkweekly.com
**Owner:** Ryan Arbuckle
**Scope:** UX/UI/visual enhancements to the existing Hugo site. Not content, not pipeline logic, except where a front-end goal depends on a pipeline fix.

---

## 0. How to use this document

Load this into the Modern Work Weekly Claude Project as standing context. It captures:

- the current observed state of the site,
- the constraints that govern every front-end decision,
- what was considered and explicitly rejected, and why,
- a sequenced build order with acceptance criteria per phase.

When starting work on any phase, read Section 3 (Constraints) and Section 6 (Deploy) first. Those two sections are where most avoidable mistakes live.

This document pairs with the existing `modern-work-weekly-ops` skill, which owns the pipeline runbook. Where the two overlap (deploy behavior, classification), the ops skill is authoritative and this document defers to it.

**Standing process rule (added round 2):** every enhancement in this document — visual, structural, or pipeline — is prototyped and reviewed before it goes live on the production site. "Prototyped" means either a chat/sandbox mockup or a preview build, not a direct commit to `main`. This applies across every phase below, not just the ones marked higher risk.

---

## 1. Current state (observed 2026-08-08)

### Stack
- Hugo 0.128.0, static output
- Caddy on a Proxmox LXC (`<your-lxc-ip>`, hostname `mww`)
- Cloudflare Tunnel fronting
- Build artifacts rsync'd from `/opt/modern-work-weekly/repo/site/public/` to `/opt/modern-work-weekly/site/public/`

### What already exists and works
- **Command palette.** `/` or `Ctrl+K` opens, `↵` opens a result, `Esc` closes. Footer documents the shortcuts. This is the highest-value power-user pattern and it is already shipped. Do not rebuild it.
- **Impact indicators.** Each digest card carries an action-item count and a CVE count ("6 action items", "12 CVEs"). This is the Clerk/GitHub pattern already in place. Preserve it, do not dilute it.
- **Pillar chips** on each digest card.
- **Tag taxonomy** with per-tag archive pages under `/tags/`.
- **Portals dropdown** with Chrome/Edge/private-window launchers for admin.cloud.microsoft, Partner Center, M365 Lighthouse. This is a genuinely differentiated utility feature and worth protecting in any redesign.
- **Key Dates** page at `/deadlines/`, including a `watching` array for undated items, rendered in a separate dashed-border section. Countdown badges and stat strip are client-side rendered (added 2026-07-31).
- **Known Issues** health page at `/health/`, fed by `site/data/health.json`, refreshed every 8 hours by `health-run.sh`.
- OG card, Twitter summary_large_image, RSS at `/index.xml`.

### Problems identified

**P1. Homepage weight.** The homepage renders the full Known Issues corpus inline, above the digest content: 21 Intune, 16 Windows 365, 23 Autopilot, 5 Defender XDR, 4 Purview, 16 Entra ID, 7 Windows Release Health. That is roughly 90+ external links and a substantial block of HTML on the most-trafficked route, positioned ahead of the content people came for. This is the single largest performance and hierarchy problem on the site, and it has nothing to do with 3D or animation.

**P2. Pillar taxonomy drift.** Two schemes coexist in the published archive:

- **Current scheme (5 pillars),** used on 2026-07-21 and 2026-08-04, and the scheme `classify_item()` / `SOURCE_PILLARS` / `CLASSIFICATION_KEYWORDS` actually target: Identity & Access, Endpoint & Device Management, Collaboration & Productivity, AI & Copilot, Security & Compliance.
- **Legacy scheme (6 Zero Trust pillars),** used 2026-05-17 through 2026-07-14: Identity, Devices, Apps, Data, Network, Visibility & Automation.

Any pillar-driven navigation is blocked until the archive is consistent. This is a content backfill, not a design decision. **This is now Phase 1 — see §5.**

**P3. Tag sprawl.** The 2026-06-16 post carries 20+ tags. At that density tags stop functioning as navigation and become visual noise on the card. Several tags appear on nearly every post (`modern-work`, `zero-trust`), which means they carry near-zero discriminating information.

**P4. No brand surface.** `/about/` exists but there is no page that communicates why this project exists or who is behind it. For a site that doubles as professional positioning, this is a missed asset.

**P5. Stale-data affordance.** "Scraped 2026-08-07" and "Last checked 2026-07-28" appear as bare text. For an operational tool, freshness is a trust signal and deserves a real visual treatment, especially where the two timestamps disagree by ten days.

---

## 2. Design goals

In priority order. Where two conflict, the higher one wins.

1. **Speed is the feature.** The audience is engineers checking a change digest, often mid-task, often on mobile, often on corporate networks. A slow load is a bounce. Every enhancement must justify its bytes.
2. **Scannability over immersion.** The primary job is "tell me what changed and what I have to act on." Anything that delays that answer is a regression regardless of how good it looks.
3. **Keyboard-native.** The audience lives in terminals and admin portals. Lean into that. The existing command palette is the model.
4. **Progressive enhancement, always.** Every visual enhancement degrades to a working page. No feature may be load-bearing for content access.
5. **Credibility through restraint.** The aesthetic target is instrument panel, not marketing site. Dense, precise, calm. Whitespace reads as confidence.

---

## 3. Hard constraints

These are non-negotiable and apply to every phase.

### Performance budget
- **Homepage HTML (uncompressed): under 100 KB.** Currently over budget because of P1.
- **Zero render-blocking JavaScript on the homepage and post routes.** The command palette and Key Dates countdown may load deferred.
- **No web fonts on the critical path.** If custom fonts are used, `font-display: swap` with a system stack fallback.
- **LCP target under 1.2s on a cold 4G connection.**
- **No JavaScript framework.** Hugo templates, CSS, and vanilla JS only.

### Weight budgeting is per-route, not per-site
This is the principle that resolves the "I want an immersive About page but I refuse a heavy site" tension.

- `/` and `/posts/*` are arrival routes. Nobody chose to be there; they clicked a link from LinkedIn or an RSS reader. Budget: minimal.
- `/about/` and `/universe/` are destination routes. Visitors there have already decided the site is worth exploring. Budget: generous.

Do not average the budget across the site. Enforce it per route.

### Accessibility
- All animation gated behind `@media (prefers-reduced-motion: reduce)`.
- Horizontal scroll containers must be keyboard-navigable and expose scroll markers.
- No content reachable only through an animation or scroll interaction. Every item in a "room" must also exist in a flat, linkable archive.
- Color-coded pillar badges must not rely on color alone. Pair with text labels.
- Color tokens (pillar palette) must be defined so a `prefers-color-scheme: dark` variant is a token swap, not a rebuild. Dark mode is in scope — see §4.

### Never do
- **Do not hijack the mouse wheel.** Horizontal scroll containers must respond to native gestures only. Wheel hijacking is the single most reliable way to make someone leave. This applies to any WebGL canvas on the page as much as it does to a CSS scroll container — the globe must never intercept scroll or drag input meant for page navigation.
- **Do not gate content behind JS.** The digest must be readable with JS disabled.
- **Do not load 3D assets on arrival routes.** `/universe/` is a destination route (see the per-route budgeting section above) and is exempt from this line; `/` and `/posts/*` are not, and never will be.
- **Do not use em-dashes** in any generated copy, per house style.
- **Do not ship anything without a prototype pass first.** See the standing process rule in §0.

---

## 4. Decisions

### Adopted

| Decision | Rationale |
|---|---|
| **News Universe page** at `/universe/` (renamed from "News Room" — round 2), two connected views: an outer Tag Universe Globe and an inner set of horizontal scroll-snap rooms, one per pillar | "News Room" undersold what this actually is — it's not a flat list, it's an exploratory view of the same dataset the globe already visualizes. "News Universe" ties the outer globe and inner rooms together as one named thing instead of two loosely related features, and reuses the globe's own "Tag Universe" working name so the branding is consistent. |
| **Complements `/tags/`, does not replace it.** (Resolves open question #1 from round 1.) | `/tags/` is the flat, exhaustive, linkable archive every accessibility requirement in §3 depends on. News Universe is a browsing lens on top of the same data, not a substitute index. |
| **Dark mode is in scope, via the same color-token system.** (Resolves the round-1 "deferred" item.) | Cheap if the Phase 4/backfill color tokens are structured for it from the start (a `prefers-color-scheme: dark` variant swaps CSS custom properties), expensive to retrofit later. Doing it now avoids a second pass through every surface that uses pillar color. |
| **Tag cap raised to 8-10** (was 6-8 in round 1), ranked by specificity, using whatever count is actually available up to that ceiling | Confirmed: more than that is noise, but 6-8 was cutting it closer than necessary. 8-10 keeps tags functioning as navigation while giving posts with genuinely broad coverage a bit more room. |
| **Pure CSS and server-rendered HTML for the room content.** `scroll-snap-type: x mandatory`, `::scroll-marker`, `::scroll-button()` | The structure comes from CSS, not from any WebGL layer sitting on top of it. This is the layer that must work with the globe absent, WebGL unsupported, or JS disabled. |
| **Tag Universe Globe as the outer shell of News Universe.** Translucent sphere, tags as glowing stars clustered by pillar, edges weighted by weekly co-occurrence; canvas-drawn textures only, no model or texture assets | Prototyped independently and is now functionally complete for its own scope (rotation, hover, fade-around-curvature, per-cluster spacing, flyout stats). What remains is route integration, not further prototyping of the sphere itself. See Phase 2 in §5. |
| **Brand story on `/about/`**, single full-viewport GLSL fragment shader | Delivers the IVRESS atmosphere. A raw fragment shader has no models, no textures, no scene graph, so it is a few KB of code rather than megabytes of assets. Destination route, so the budget allows it. |
| **Native view transitions** via `@view-transition { navigation: auto; }` | Gives a static multi-page Hugo site app-like continuity for two lines of CSS. Firefox falls back to a normal cross-fade. |
| **CSS scroll-driven animations** for reading progress and section reveals | `animation-timeline: scroll()` / `view()` runs on the compositor thread. Degrades perfectly: unsupported browsers show the end state, so content is never hidden. |
| **News Universe is a new page, not a homepage replacement** | The homepage's job ("here is this week, here is what needs action") is different from News Universe's ("browse by domain"). Both are valid; neither substitutes for the other. |

### Rejected

| Rejected | Reason |
|---|---|
| **Hubtown-style 3D hero** (hubtown.co.in) | Too heavy. The weight is model files, textures, GSAP, and a full scene graph, not "3D" per se. Fails the speed goal. |
| **Three.js for the News Room** (original round-1 phrasing) | Unnecessary as a navigation structure — CSS does that job at zero cost. *(Amendment, round 1: this doesn't extend to 3D-as-optional-atmosphere around unchanged CSS navigation, which is what News Universe actually does. See the Adopted row above.)* |
| **3D anywhere on `/` or `/posts/*`** | Arrival routes. Non-negotiable. |
| **A second command palette or search UI** | Already shipped and working. |
| **Full redesign** | The information architecture is fundamentally sound. These are additive enhancements to a working site. |

### Deferred / open

- Whether a per-pillar RSS feed should accompany the rooms. Still undecided as of round 2.

---

## 5. Build order

**Re-sequenced in round 2.** The original phase order optimized purely for risk (lowest risk first). Ryan's direction: content backfill first regardless of its risk level, because it's a prerequisite for News Universe; News Universe second, because it's the reason the backfill matters; then everything else, *now* ordered low risk to high risk, each one prototyped before it ships. Phase numbers below reflect this new execution order, not the original document's numbering.

---

### Phase 1: Legacy content backfill
**Goal:** Bring every published post onto the current 5-pillar taxonomy, the new 8-10 tag cap, and a verified freshness check — before News Universe is built on top of it.

**Changes:**
- Confirm the canonical pillar set: Identity & Access, Endpoint & Device Management, Collaboration & Productivity, AI & Copilot, Security & Compliance.
- Backfill legacy posts (2026-05-17 through 2026-07-14) from the 6-pillar Zero Trust labels to the current 5. Starting map, to be reviewed per post rather than applied blindly:
  - Identity → Identity & Access
  - Devices → Endpoint & Device Management
  - Apps → Collaboration & Productivity (audit; some "Apps" items are Copilot/Power Platform and belong in AI & Copilot)
  - Data → Security & Compliance
  - Network → Identity & Access (Global Secure Access items) or Security & Compliance, case by case
  - Visibility & Automation → split by item; no clean single target
- Where the mapping is ambiguous, pull the week's `state/archive/pending_draft_<week>.json` and check each item's `source` and `category_matched` fields rather than guessing from the label.
- While each post is open for editing anyway, also cap its tags at 8-10 (ranked by specificity, using the same logic the round-2 tag cap defines for new posts) and drop near-universal tags (`modern-work`, `zero-trust`) from the visible tag list on the card, keeping them in front matter for `/tags/` archive purposes.
- Verify freshness for each legacy week: confirm every item's original recorded date falls within the 7-day window of that week's specific digest date. This is an audit against already-recorded data, not a re-scrape — the goal is to catch any item that shouldn't have cleared the freshness filter at the time, not to re-run the scraper against the past.
- Define the 5 canonical pillar colors as CSS custom properties now, including a `prefers-color-scheme: dark` variant. Both the reconciled cards and News Universe (Phase 2) read from this one token set — do not let either maintain its own palette.

**Process (per the ops runbook, non-negotiable):**
- These are published posts. Anything already shared externally (LinkedIn) must be **surgically hand-edited**, never regenerated. A `digest.py` regen makes a fresh non-deterministic Top 5 selection and will break outbound links from already-published LinkedIn newsletters. Hand-edit front matter, pillar chips, and the tag list only — do not touch Top 5.
- **1-by-1 review for the first few weeks**, per Ryan's explicit direction — no batch pass until the approach is validated on a couple of weeks. Start with the earliest legacy week (2026-05-17), present the proposed diff before committing, then proceed week by week.

**Acceptance criteria:**
- Every post in `/posts/` uses only the 5 canonical pillar labels.
- No post card displays more than 10 tags, and near-universal tags are hidden from the card (still present in front matter).
- Every legacy week's items are confirmed within the 7-day freshness window of that week's date; any exception is flagged, not silently kept.
- Front matter YAML still parses on every edited file.
- `git diff --stat` shows a small, clean change per file. Hundreds of lines means CRLF drift from OneDrive; run `sed -i 's/\r$//'` and re-check before committing.
- Top 5 sections byte-identical to what was published.
- The 5 pillar color tokens (including dark-mode variant) exist as CSS custom properties before Phase 2 starts.

**Risk:** Medium — touches published content — but sequenced first regardless, because News Universe depends on it. Follow the surgical-edit path in the ops runbook and the 1-by-1 review process above.

---

### Phase 2: News Universe
**Goal:** Ship the two connected views at `/universe/` — outer Tag Universe Globe, inner pillar rooms — on top of the now-reconciled taxonomy and shared color tokens from Phase 1.

**Depends on:** Phase 1 (taxonomy and color tokens must exist first).

**Changes:**
- **Outside view — the Tag Universe Globe.** Functionally complete as prototyped: translucent sphere, tags clustered by pillar and sized by frequency, edges weighted by weekly co-occurrence, camera auto-rotates and pauses only on direct star hover (which opens the flyout), stars fade smoothly around the curvature instead of popping, per-pillar sunflower-spiral layout so no two tags ever share a point. Remaining work here is integration, not further prototyping: wire it to real data via a `generate_graph.py`-style script (analogous to `generate_search_index.py`), pull colors from the Phase 1 tokens instead of its own hard-coded palette, add the dark-mode variant, and route-scope the JS so it never loads on `/` or `/posts/*`.
- **Inside view — the rooms.** `display: grid; grid-auto-flow: column; overflow-x: auto; scroll-snap-type: x mandatory;`, five rooms (the canonical pillars from Phase 1), `::scroll-button()` / `::scroll-marker` navigation, `@supports`-gated scroll-driven entry animation. Pure CSS plus server-rendered HTML; works completely with the globe absent or WebGL unsupported.
- **Transition between the two views:** a real, keyboard-operable control (a button, or clicking a pillar's star cluster) — never a scroll-hijack, and never a wheel or drag interception on the globe canvas that fights page scroll. Clicking a pillar in the outer view scrolls the inner room container to that pillar's `::scroll-marker` position. A camera fly-through into the globe is a nice-to-have, not a v1 requirement — a cut or CSS cross-fade between views is sufficient for launch.
- Each room contains: pillar name and color header, the 3-4 most recent items in that pillar across all weeks, a rolling action-item count for that pillar, and a "View all in {pillar} →" link into the flat `/tags/` archive. News Universe complements `/tags/`, it is never the only path to an item.
- Lazy-load the globe below the fold or behind a "view as globe" control, gated behind `@supports` for WebGL, and killed entirely under `prefers-reduced-motion: reduce` and `navigator.connection.saveData`.

**Acceptance criteria:**
- With JavaScript disabled, or WebGL unsupported, `/universe/` renders as the plain five-room CSS scroll container with all content intact. No globe, no missing content, no broken layout.
- With CSS disabled, all room content is present and readable as a linear document.
- Native trackpad, touch, and keyboard scrolling all work in the inner view. No wheel interception, including by the globe canvas when present.
- Tab order moves through rooms in visual order and scrolls the container into view; the globe, if present, is not a tab stop that traps focus.
- Every item in every room is also reachable from `/posts/` or `/tags/`.
- Dark mode works in both views, reading from the Phase 1 tokens.
- On mobile: the globe either does not load (reduced motion / data saver) or is touch-draggable at the same interaction model as the prototype; rooms remain swipeable and full-viewport-width regardless.
- Globe JS and any related assets are route-scoped to `/universe/` and do not appear in the shared bundle used by `/` or `/posts/*`.
- Prototyped and reviewed before it ships, per the standing process rule in §0.

**Risk:** Medium-high — the most new surface area of any phase — but sequenced second regardless of risk, per explicit direction. The globe sphere itself is done; the remaining risk is in the integration and the outer/inner transition, so prototype that specifically before wiring it to production content.

---

### Phase 3: Homepage diet
**Goal:** Remove the Known Issues corpus from the homepage. Replace with a compact tile row.

**Changes:**
- Modify the homepage layout to read `site/data/health.json` for *counts only*, not the item arrays.
- Render one tile per source area: Intune (21), Windows 365 (16), Autopilot (23), Defender XDR (5), Purview (4), Entra ID (16), Windows Release Health (7).
- Each tile links to the corresponding anchor on `/health/`.
- Retain the "View all known issues →" link and the Live Status external link.
- Move the tile row *below* the current week's digest card. The week's digest is the reason people came.

**Acceptance criteria:**
- Homepage HTML under 100 KB uncompressed.
- The full known-issues detail remains reachable and complete at `/health/`.
- No loss of any link currently present on the homepage; they relocate, they do not disappear.
- The current week's digest card is the first content block after the header.
- Prototyped and reviewed before it ships.

**Risk:** Low. Template-only change, no pipeline impact.

---

### Phase 4: Native view transitions
**Goal:** App-like continuity between archive and post routes.

**Changes:**
- Add `@view-transition { navigation: auto; }` to the main stylesheet.
- Assign `view-transition-name` to the elements that persist across navigation: the digest card title (to the post `h1`), the site header, the pillar chip row.
- Gate custom transition animations behind `prefers-reduced-motion`.

**Acceptance criteria:**
- Navigation from homepage card to post animates the shared title element in Chromium and Safari.
- Firefox shows a plain cross-fade with no errors.
- Zero added JavaScript.
- No layout shift introduced on either route.
- Prototyped and reviewed before it ships.

**Risk:** Low. Purely additive CSS.

---

### Phase 5: Remaining badge-system polish
**Goal:** Finish what Phase 1's tag-cap-and-token work didn't already cover: apply the shared pillar tokens everywhere, and add a severity indicator.

**Changes:**
- Apply the Phase 1 pillar color tokens to every remaining surface that shows pillar identity: section headers within posts, any place not already covered by the Phase 1 backfill or Phase 2 News Universe.
- Confirm pillar identity is legible in grayscale (color is never the only signal — text label is paired everywhere).
- Consider extending the existing action-item/CVE counts with a severity indicator, following the GitHub changelog pattern of visually distinguishing major from minor.
- Confirm the dark-mode token variant (defined in Phase 1) is wired up sitewide, not just on the surfaces Phase 1 and 2 touched directly.

**Acceptance criteria:**
- The 5 pillar colors are referenced from the single Phase 1 token set everywhere they appear, with no second hard-coded palette anywhere in the codebase.
- Pillar identity is readable in grayscale.
- Dark mode is consistent across every route that shows pillar color.
- Prototyped and reviewed before it ships.

**Risk:** Low-medium. Mostly template/CSS reference cleanup at this point, since the heavier lifting (defining tokens, capping tags) already happened in Phase 1.

---

### Phase 6: Brand story on /about/
**Goal:** Atmospheric About page communicating what Modern Work Weekly is and who builds it.

**Changes:**
- Rewrite `/about/` as a scroll-sequenced narrative: origin, method (how the pipeline actually works, which is itself the credibility argument), sources, and author.
- Single full-viewport GLSL fragment shader as the hero backdrop. No geometry, no models, no textures. Target a few KB of shader source.
- Lazy-load the shader below the fold. The page must render and be readable at first paint with no shader running.
- Kill the shader entirely under `prefers-reduced-motion: reduce` and on `navigator.connection.saveData`.
- Pair with scroll-driven section reveals.

**Acceptance criteria:**
- `/about/` is fully readable with JS disabled.
- Shader adds under 15 KB total transfer.
- No impact to `/` or `/posts/*` bundle size. Shader code must not be in the shared stylesheet or shared JS.
- LCP on `/about/` under 2.0s. Looser than the arrival-route budget, deliberately.
- Reduced-motion users get a static gradient or flat color, not a frozen shader.
- Prototyped and reviewed before it ships.

**Risk:** Medium. Isolated route, so the blast radius is contained, but it is the phase that spends the most real bytes — sequenced last for that reason.

---

## 6. Deploy notes for front-end changes

Front-end work touches `site/layouts/*` and `site/assets/*`, which **are** part of the Hugo build, unlike `scraper/*.py` changes. That means every phase here is subject to the `deploy.sh` drift gotcha documented in the ops runbook.

**Before assuming a front-end change failed:**

1. Confirm GitHub has it: `https://raw.githubusercontent.com/TwitchSTL/modern-work-weekly/main/<path>`
2. On the LXC, check for the drift pattern: `git status` showing modified `site/data/deadlines.json` or `health.json`, combined with HEAD behind `origin/main`.
3. Discard drift and pull:
   ```bash
   git checkout -- site/data/deadlines.json site/data/health.json
   git pull
   ```
4. Force the rebuild, because `deploy.sh` will see `BEFORE == AFTER` and skip:
   ```bash
   cd /opt/modern-work-weekly/repo/site
   hugo --minify --baseURL "https://modernworkweekly.com"
   rsync -av --delete public/ /opt/modern-work-weekly/site/public/
   ```

**Standing recommendation, still unapplied as of the last incident:** add `git checkout -- site/data/health.json site/data/deadlines.json 2>/dev/null || true` to `deploy.sh` immediately before its `git pull`, matching `weekly-run.sh` and `health-run.sh`. This makes `deploy.sh` self-heal instead of logging an error nobody reads. Small diff, low risk, addresses the root cause. Worth doing before Phase 1 starts, since a full-archive backfill means many small commits and many chances to hit the same silent-stall pattern.

**Verification caveat:** anything rendered client-side (Key Dates countdown badges, and any JS added in these phases) will not appear in a raw HTTP fetch. Server-rendered content is verifiable that way; client-rendered content needs a real browser check.

---

## 7. Reference examples

Sites the adopted patterns were drawn from, for visual reference during implementation:

| Pattern | Reference |
|---|---|
| Scene per item, scroll between rooms | Cartier Watches & Wonders, `cartier.com/en-fr/watchesandwonders` |
| Scroll as narrative device on a changelog | Shopify Editions, `shopify.com/editions/spring2026` |
| Shader atmosphere without asset weight | IVRESS, `brand.ivress.co.jp` |
| Editorial pacing in a scroll-driven scene | Sleep Well Creative, `sleep-well-creatives.com` |
| Whitespace and typography in a changelog | Linear, `linear.app/changelog` |
| Color-coded category badges | Clerk, `clerk.com/changelog` |
| Impact-level indicators, category filters | GitHub, `github.blog/changelog` |
| Categorized filtering with mobile-first behavior | Stripe, `docs.stripe.com/changelog` |
| Scrollytelling reference | The Pudding, `pudding.cool` |

**Anti-reference:** Hubtown, `hubtown.co.in`. Visually strong, explicitly rejected on weight. Useful as a marker for the line not to cross.

---

## 8. Open questions for Ryan

Resolved in round 2 (kept here for history, no longer open): whether News Universe complements or replaces `/tags/` (complements); dark mode scope (in scope, token-driven); the page name (News Universe); the tag cap number (8-10); whether the globe needs more prototyping before integration (no — it's functionally complete, remaining work is integration per Phase 2).

Still open:

1. Should each pillar get its own RSS feed alongside its room? Still undecided.
2. Is any of the May-July archive already linked from published LinkedIn newsletters? That determines the exact surgical-edit approach for each specific week in Phase 1 — flagged per week during the 1-by-1 review rather than assumed up front.
3. The homepage shows "Scraped 2026-08-07" and Key Dates shows "Last checked 2026-07-28." Is that ten-day gap expected, or is it the `deadline_candidates.json` human-in-the-loop step being skipped, as flagged in the ops runbook? Worth checking before Phase 1's freshness audit, since it may explain a pattern seen across multiple weeks rather than being a one-off.
4. Does the outer globe need a real "fly into the pillar" camera animation for v1, or is a cut/cross-fade into the inner room acceptable? A camera fly-through is a materially bigger build than a cut, and Phase 2 currently assumes the cut/cross-fade for launch.
5. Should the globe be the default view when `/universe/` loads, or should the rooms load first with the globe reachable as an optional toggle? Affects perceived load speed on a route that already carries a generous, but not unlimited, budget.
