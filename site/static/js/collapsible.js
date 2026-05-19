/**
 * collapsible.js — Makes digest post sections expandable/collapsible.
 *
 * - Top 5 items: title-only summary, body expands on click
 * - Category sections (h2): shows item count + preview titles, full list expands on click
 *
 * Pure progressive enhancement — works without JS, just not collapsible.
 */

document.addEventListener('DOMContentLoaded', function () {
  const content = document.querySelector('.post-content');
  if (!content) return;

  makeTop5Collapsible(content);
  makeSectionsCollapsible(content);

  // Hide hr separators — section borders replace them visually
  content.querySelectorAll('hr').forEach(hr => hr.style.display = 'none');
});


/* ── Top 5 ────────────────────────────────────────────────────────────── */

function makeTop5Collapsible(content) {
  // Find the h2 that contains "Top 5"
  let top5OL = null;
  content.querySelectorAll('h2').forEach(h2 => {
    if (!h2.textContent.toLowerCase().includes('top 5')) return;
    let next = h2.nextElementSibling;
    while (next && next.tagName !== 'H2') {
      if (next.tagName === 'OL') { top5OL = next; break; }
      next = next.nextElementSibling;
    }
  });
  if (!top5OL) return;

  const wrapper = document.createElement('div');
  wrapper.className = 'top5-list';

  let index = 1;
  Array.from(top5OL.querySelectorAll('li')).forEach(li => {
    const strong = li.querySelector('strong');
    if (!strong) return;

    const details = document.createElement('details');
    details.className = 'top5-item';
    details.open = false; // collapsed by default

    const summary = document.createElement('summary');
    summary.className = 'top5-summary';
    summary.innerHTML =
      `<span class="top5-num">${index}.</span>` +
      `<span class="top5-title">${strong.innerHTML}</span>` +
      `<span class="top5-arrow">›</span>`;

    const body = document.createElement('div');
    body.className = 'top5-body';
    // Strip the leading strong tag and any leading punctuation/dash
    const fullHTML = li.innerHTML;
    const afterStrong = fullHTML.slice(fullHTML.indexOf(strong.outerHTML) + strong.outerHTML.length);
    body.innerHTML = afterStrong.replace(/^\s*[—–-]\s*/, '').trim();

    details.appendChild(summary);
    details.appendChild(body);
    wrapper.appendChild(details);
    index++;
  });

  top5OL.replaceWith(wrapper);
}


/* ── Category sections (h2) ───────────────────────────────────────────── */

function makeSectionsCollapsible(content) {
  const h2s = Array.from(content.querySelectorAll('h2'));

  h2s.forEach(h2 => {
    if (h2.textContent.toLowerCase().includes('top 5')) return;

    // Collect everything between this h2 and the next h2
    const siblings = [];
    let next = h2.nextElementSibling;
    while (next && next.tagName !== 'H2') {
      siblings.push(next);
      next = next.nextElementSibling;
    }
    if (siblings.length === 0) return;

    // Build preview: first 3 bold item titles
    const tempDiv = document.createElement('div');
    siblings.forEach(s => tempDiv.appendChild(s.cloneNode(true)));
    const boldItems = Array.from(tempDiv.querySelectorAll('li strong, li b'));
    const preview = boldItems.slice(0, 3).map(b => b.textContent.trim()).join(' · ');
    const itemCount = tempDiv.querySelectorAll('li').length;

    // Build details block
    const details = document.createElement('details');
    details.className = 'section-collapsible';

    const summary = document.createElement('summary');
    summary.className = 'section-summary';
    summary.innerHTML =
      `<div class="section-summary-top">` +
        `<span class="section-title">${h2.textContent}</span>` +
        `<span class="section-meta">${itemCount} item${itemCount !== 1 ? 's' : ''}</span>` +
      `</div>` +
      (preview ? `<span class="section-preview">${preview}</span>` : '');

    details.appendChild(summary);
    siblings.forEach(sib => details.appendChild(sib));

    h2.parentNode.insertBefore(details, h2);
    h2.remove();
  });
}
