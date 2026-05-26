/**
 * collapsible.js — Makes digest post sections expandable/collapsible.
 *
 * Top 5 items: numbered badge + title visible, body expands on click
 * Category sections: title + item count + preview visible, list expands on click
 *
 * Front matter flags (via data attributes on .post-content):
 *   data-expand-all="true"   — all sections open by default (intro/about posts)
 *   data-no-counters="true"  — hide the (N items) badge
 */

// Zero Trust pillar colors — ordered longest-key-first for partial matching
const PILLAR_COLORS = [
  { keys: ['visibility & automation', 'automation & ai', 'ai & automation'],  color: '#d2a8ff' },
  { keys: ['collaboration & productivity'],                                    color: '#58a6ff' },
  { keys: ['identity & access', 'identity'],                                  color: '#a78bfa' },
  { keys: ['endpoint management', 'devices'],                                  color: '#3fb950' },
  { keys: ['security & compliance', 'data'],                                  color: '#f0883e' },
  { keys: ['network'],                                                         color: '#39d353' },
  { keys: ['apps'],                                                            color: '#58a6ff' },
  { keys: ['action required', 'action items', 'recommended actions'],         color: '#ff6b6b' },
];

function categoryColor(name) {
  const n = name.toLowerCase().trim();
  for (const { keys, color } of PILLAR_COLORS) {
    for (const key of keys) {
      if (n.includes(key)) return color;
    }
  }
  return '#6e7681'; // neutral gray fallback
}

// Detect ZT pillar from Top 5 item text
function detectPillar(text) {
  const t = text.toLowerCase();
  if (/entra|azure ad|\bmfa\b|passkey|\bsso\b|\bpim\b|identity|conditional access|\bcba\b|entitlement/.test(t)) return 'identity';
  if (/intune|autopatch|\bmdm\b|device|endpoint|macos|android|apple|windows update|\bepm\b|laps/.test(t)) return 'devices';
  if (/teams|sharepoint|onedrive|outlook|copilot|viva|loop|planner|yammer|forms/.test(t)) return 'apps';
  if (/purview|\bdlp\b|sensitivity label|insider risk|compliance|data governance|retention|ediscovery/.test(t)) return 'data';
  if (/global secure access|\bztna\b|firewall|network|private access|internet access/.test(t)) return 'network';
  if (/defender|sentinel|threat|incident|hunting|\bxdr\b|\bsiem\b|secure score|vulnerability|agent|api|automation/.test(t)) return 'visibility & automation';
  return 'visibility & automation';
}

document.addEventListener('DOMContentLoaded', function () {
  const content = document.querySelector('.post-content');
  if (!content) return;

  const expandAll  = content.dataset.expandAll  === 'true';
  const noCounters = content.dataset.noCounters === 'true';

  makeTop5Collapsible(content, expandAll);
  makeSectionsCollapsible(content, expandAll, noCounters);
  content.querySelectorAll('hr').forEach(hr => hr.style.display = 'none');

  // If navigating here from a search result, auto-open the target section.
  const hash = window.location.hash.slice(1);
  if (hash) {
    const target = document.getElementById(decodeURIComponent(hash));
    if (target && target.tagName === 'DETAILS') {
      target.open = true;
      setTimeout(function () {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 80);
    }
  }
});


/* ── Top 5 ────────────────────────────────────────────────────────────── */

function makeTop5Collapsible(content, expandAll) {
  let top5OL  = null;
  let top5H2  = null;

  content.querySelectorAll('h2').forEach(h2 => {
    if (!h2.textContent.toLowerCase().includes('top 5')) return;
    top5H2 = h2;
    let next = h2.nextElementSibling;
    while (next && next.tagName !== 'H2') {
      if (next.tagName === 'OL') { top5OL = next; break; }
      next = next.nextElementSibling;
    }
  });

  if (!top5OL) return;

  const section = document.createElement('div');
  section.className = 'top5-section';

  const heading = document.createElement('div');
  heading.className = 'top5-heading';
  heading.textContent = top5H2 ? top5H2.textContent : 'Top 5 This Week';
  section.appendChild(heading);

  const list = document.createElement('div');
  list.className = 'top5-list';

  let index = 1;
  Array.from(top5OL.querySelectorAll('li')).forEach(li => {
    const strong = li.querySelector('strong');
    if (!strong) return;

    const pillar  = detectPillar(li.textContent);
    const color   = categoryColor(pillar);

    const details = document.createElement('details');
    details.className = 'top5-item';
    details.style.borderLeftColor = color;
    if (expandAll) details.open = true;

    const summary = document.createElement('summary');
    summary.className = 'top5-summary';

    const badge = document.createElement('span');
    badge.className = 'top5-badge';
    badge.textContent = index;
    badge.style.background = color;

    const title = document.createElement('span');
    title.className = 'top5-title';
    title.innerHTML = strong.innerHTML;

    const chevron = document.createElement('span');
    chevron.className = 'top5-chevron';

    summary.appendChild(badge);
    summary.appendChild(title);
    summary.appendChild(chevron);

    const body = document.createElement('div');
    body.className = 'top5-body';
    const fullHTML  = li.innerHTML;
    const afterStrong = fullHTML.slice(fullHTML.indexOf(strong.outerHTML) + strong.outerHTML.length);
    body.innerHTML  = afterStrong.replace(/^\s*[—–\-\.]\s*/, '').trim();

    details.appendChild(summary);
    details.appendChild(body);
    list.appendChild(details);
    index++;
  });

  section.appendChild(list);
  if (top5H2) top5H2.replaceWith(section);
  top5OL.remove();
}


/* ── Category sections (h2) ───────────────────────────────────────────── */

function makeSectionsCollapsible(content, expandAll, noCounters) {
  const h2s = Array.from(content.querySelectorAll('h2'));

  h2s.forEach(h2 => {
    const titleText = h2.textContent.trim();
    if (titleText.toLowerCase().includes('top 5')) return;

    const siblings = [];
    let next = h2.nextElementSibling;
    while (next && next.tagName !== 'H2') {
      siblings.push(next);
      next = next.nextElementSibling;
    }
    if (siblings.length === 0) return;

    // Count items: li bullets (new format) + h3 headings (legacy format)
    const tempDiv = document.createElement('div');
    siblings.forEach(s => tempDiv.appendChild(s.cloneNode(true)));
    const itemCount = tempDiv.querySelectorAll('li, h3').length;

    // Preview: first 3 bold item titles (or h3 headings for legacy format)
    const boldItems = Array.from(tempDiv.querySelectorAll('li strong, li b, h3'));
    const preview   = boldItems.slice(0, 3).map(b => b.textContent.trim()).join('  ·  ');

    const color = categoryColor(titleText);

    const details = document.createElement('details');
    details.className = 'section-collapsible';
    details.style.borderLeftColor = color;
    // Preserve the h2's ID so anchor links still work
    if (h2.id) details.id = h2.id;

    // Auto-expand: action sections always open; everything open when expandAll is set
    const tl = titleText.toLowerCase();
    const isAction = tl.includes('action') || tl.includes('deadline') || tl.includes('required') || tl.includes('recommended');
    if (expandAll || isAction) details.open = true;

    const summary = document.createElement('summary');
    summary.className = 'section-summary';

    const row = document.createElement('div');
    row.className = 'section-row';

    const titleSpan = document.createElement('span');
    titleSpan.className = 'section-title';
    titleSpan.textContent = titleText;
    titleSpan.style.color = color;

    const right = document.createElement('div');
    right.className = 'section-right';

    if (!noCounters) {
      const count = document.createElement('span');
      count.className = 'section-count';
      count.textContent = `${itemCount} item${itemCount !== 1 ? 's' : ''}`;
      right.appendChild(count);
    }

    const chevron = document.createElement('span');
    chevron.className = 'section-chevron';
    right.appendChild(chevron);

    row.appendChild(titleSpan);
    row.appendChild(right);
    summary.appendChild(row);

    if (preview && !noCounters) {
      const prev = document.createElement('span');
      prev.className = 'section-preview';
      prev.textContent = preview;
      summary.appendChild(prev);
    }

    details.appendChild(summary);

    // Wrap all sibling content in a section-body div for consistent padding
    const body = document.createElement('div');
    body.className = 'section-body';
    siblings.forEach(sib => body.appendChild(sib));
    details.appendChild(body);

    h2.parentNode.insertBefore(details, h2);
    h2.remove();
  });
}
