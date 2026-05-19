/**
 * collapsible.js — Makes digest post sections expandable/collapsible.
 *
 * Top 5 items: numbered badge + title visible, body expands on click
 * Category sections: title + item count + preview visible, list expands on click
 */

// Zero Trust pillar colors
const CATEGORY_COLORS = {
  // Current ZT pillar names
  'identity':                  '#a78bfa',  // purple
  'devices':                   '#3fb950',  // green
  'apps':                      '#58a6ff',  // blue
  'data':                      '#f0883e',  // amber
  'network':                   '#39d353',  // teal
  'visibility & automation':   '#d2a8ff',  // lavender
  'action required':           '#ff6b6b',  // red — always stands out
  // Legacy aliases for existing posts
  'identity & access':         '#a78bfa',
  'endpoint management':       '#3fb950',
  'collaboration & productivity': '#58a6ff',
  'security & compliance':     '#f0883e',
  'automation & ai':           '#d2a8ff',
};

// Detect ZT pillar from item text for Top 5 coloring
function detectPillar(text) {
  const t = text.toLowerCase();
  if (/entra|azure ad|\bmfa\b|passkey|\bsso\b|\bpim\b|identity|conditional access|\bcba\b|lifecycle workflow|entitlement/.test(t)) return 'identity';
  if (/intune|autopatch|\bmdm\b|device|endpoint|macos|android|apple|\btvos\b|windows update|\bepm\b|laps/.test(t)) return 'devices';
  if (/teams|sharepoint|onedrive|outlook|copilot|viva|loop|planner|yammer|forms/.test(t)) return 'apps';
  if (/purview|\bdlp\b|sensitivity label|insider risk|compliance|data governance|retention|ediscovery/.test(t)) return 'data';
  if (/global secure access|\bztna\b|firewall|network|private access|internet access/.test(t)) return 'network';
  return 'visibility & automation';
}

function categoryColor(name) {
  return CATEGORY_COLORS[name.toLowerCase().trim()] || 'var(--color-accent)';
}

document.addEventListener('DOMContentLoaded', function () {
  const content = document.querySelector('.post-content');
  if (!content) return;

  makeTop5Collapsible(content);
  makeSectionsCollapsible(content);
  content.querySelectorAll('hr').forEach(hr => hr.style.display = 'none');
});


/* ── Top 5 ────────────────────────────────────────────────────────────── */

function makeTop5Collapsible(content) {
  let top5OL = null;
  let top5H2 = null;

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

  // Build the Top 5 section wrapper
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

    const pillar = detectPillar(li.textContent);
    const pillarColor = categoryColor(pillar);

    const details = document.createElement('details');
    details.className = 'top5-item';
    details.style.setProperty('--item-color', pillarColor);

    const summary = document.createElement('summary');
    summary.className = 'top5-summary';
    summary.innerHTML =
      `<span class="top5-badge">${index}</span>` +
      `<span class="top5-title">${strong.innerHTML}</span>` +
      `<span class="top5-chevron"></span>`;

    const body = document.createElement('div');
    body.className = 'top5-body';
    const fullHTML = li.innerHTML;
    const afterStrong = fullHTML.slice(fullHTML.indexOf(strong.outerHTML) + strong.outerHTML.length);
    body.innerHTML = afterStrong.replace(/^\s*[—–\-\.]\s*/, '').trim();

    details.appendChild(summary);
    details.appendChild(body);
    list.appendChild(details);
    index++;
  });

  section.appendChild(list);

  // Replace h2 + OL with our new section
  if (top5H2) top5H2.replaceWith(section);
  top5OL.remove();
}


/* ── Category sections (h2) ───────────────────────────────────────────── */

function makeSectionsCollapsible(content) {
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

    // Build preview from first 3 bold item titles
    const tempDiv = document.createElement('div');
    siblings.forEach(s => tempDiv.appendChild(s.cloneNode(true)));
    const boldItems = Array.from(tempDiv.querySelectorAll('li strong, li b'));
    const preview = boldItems.slice(0, 3).map(b => b.textContent.trim()).join('  ·  ');
    const itemCount = tempDiv.querySelectorAll('li').length;

    const color = categoryColor(titleText);

    const details = document.createElement('details');
    details.className = 'section-collapsible';
    details.style.setProperty('--cat-color', color);

    const summary = document.createElement('summary');
    summary.className = 'section-summary';
    summary.innerHTML =
      `<div class="section-row">` +
        `<span class="section-title">${titleText}</span>` +
        `<div class="section-right">` +
          `<span class="section-count">${itemCount} item${itemCount !== 1 ? 's' : ''}</span>` +
          `<span class="section-chevron"></span>` +
        `</div>` +
      `</div>` +
      (preview ? `<span class="section-preview">${preview}</span>` : '');

    details.appendChild(summary);
    siblings.forEach(sib => details.appendChild(sib));

    // Auto-expand Action Required / deadlines sections
    const titleLower = titleText.toLowerCase();
    if (titleLower.includes('action') || titleLower.includes('deadline') || titleLower.includes('required')) {
      details.open = true;
    }

    h2.parentNode.insertBefore(details, h2);
    h2.remove();
  });
}
