/**
 * exec-nav.js — Executive's Guide section navigation and UX enhancements.
 *
 * 1. Wraps h2 sections in collapsible <details> cards with risk-color coding
 * 2. Builds a jump-to pill nav with expand/collapse all
 * 3. Builds a risk dashboard (HIGH / MED / LOW counts)
 * 4. Color-codes legacy table rows containing risk emojis
 * 5. Adds anchor share links to each section header
 * 6. Styles source citation lines as a distinct block
 * 7. Auto-opens a section OR a single card targeted by URL hash
 * 8. Surfaces the single highest-priority item as a hero alert above the fold
 * 9. Drives a thin scroll-progress bar fixed to the top of the viewport
 * 10. Turns every bullet/lead-bold paragraph into a click-to-expand,
 *     individually deep-linkable card (cardify())
 */

(function () {
  'use strict';

  var RISK = {
    HIGH: { emoji: '🔴', cls: 'exec-risk-high', rowCls: 'exec-row-high', itemCls: 'exec-item-high', label: 'High' },
    MED:  { emoji: '🟡', cls: 'exec-risk-med',  rowCls: 'exec-row-med',  itemCls: 'exec-item-med',  label: 'Medium' },
    LOW:  { emoji: '🟢', cls: 'exec-risk-low',  rowCls: 'exec-row-low',  itemCls: 'exec-item-low',  label: 'Low' },
  };

  function slugify(text) {
    return text.toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '')
      .trim()
      .replace(/\s+/g, '-');
  }

  function stripEmoji(text) {
    return text.replace(/\p{Emoji}/gu, '').replace(/⚠️/g, '').trim();
  }

  function detectRisk(text) {
    if (text.indexOf('🔴') !== -1) return RISK.HIGH;
    if (text.indexOf('🟡') !== -1) return RISK.MED;
    if (text.indexOf('🟢') !== -1) return RISK.LOW;
    return null;
  }

  function colorTableRows(container) {
    container.querySelectorAll('table tr').forEach(function (tr) {
      var text = tr.textContent || '';
      var risk = detectRisk(text);
      if (risk) tr.classList.add(risk.rowCls);
    });
  }

  // Adaptive cards — 2026-07-21 follow-up to the first redesign pass.
  // Turns every bulleted item AND every lead-bold paragraph (e.g. "If You
  // Take No Action") into a click-to-expand card: bold title + risk color
  // visible immediately, full sentence collapsed until clicked. Replaces
  // the earlier colorListItems() (which only added a color class) since
  // this does that AND restructures for scanability. Built so a reader
  // with ~30 seconds can scan titles across a section and only open what
  // matters to them, and so any single item can be deep-linked directly.
  var usedSlugs = {};
  function uniqueSlug(base) {
    var slug = base || 'item';
    var n = 1;
    while (usedSlugs[slug]) { slug = base + '-' + (++n); }
    usedSlugs[slug] = true;
    return slug;
  }

  function cardifyOne(el, idx) {
    // Markdown renders a "loose" list (blank lines between bullets in the
    // source — true for Risk & Compliance, Planning Horizon, etc.) by
    // wrapping each <li>'s content in its own <p>. A "tight" list (no
    // blank lines — true for Week at a Glance) doesn't. Unwrap the <p> so
    // the rest of this function sees the same shape either way.
    if (el.tagName === 'LI' && el.childNodes.length === 1 &&
        el.firstElementChild && el.firstElementChild.tagName === 'P') {
      var innerP = el.firstElementChild;
      while (innerP.firstChild) el.appendChild(innerP.firstChild);
      el.removeChild(innerP);
    }

    var strong = el.querySelector('strong');
    if (!strong) return;

    // Only treat a <p> as a card if it genuinely LEADS with the bold text
    // (e.g. "**Item:** rest of sentence") — otherwise it's ordinary prose
    // with an incidental bold phrase and should stay a plain paragraph.
    if (el.tagName === 'P') {
      var leadsWithStrong = el.textContent.trim().indexOf(strong.textContent.trim()) === 0;
      if (!leadsWithStrong) return;
    }

    var topNode = strong;
    while (topNode.parentNode && topNode.parentNode !== el) topNode = topNode.parentNode;
    if (topNode.parentNode !== el) return; // unexpected nesting — leave as-is

    var headNodes = [], bodyNodes = [], seenTop = false;
    Array.prototype.forEach.call(el.childNodes, function (n) {
      if (n === topNode) { headNodes.push(n); seenTop = true; }
      else if (!seenTop) headNodes.push(n);
      else bodyNodes.push(n);
    });
    if (!bodyNodes.length) return; // nothing to collapse — leave as a plain line

    var headFrag = document.createDocumentFragment();
    headNodes.forEach(function (n) { headFrag.appendChild(n.cloneNode(true)); });
    var bodyFrag = document.createDocumentFragment();
    bodyNodes.forEach(function (n, i) {
      var clone = n.cloneNode(true);
      if (i === 0 && clone.nodeType === 3) {
        clone.textContent = clone.textContent.replace(/^[\s:–—-]+/, '');
      }
      bodyFrag.appendChild(clone);
    });

    var risk = detectRisk(el.textContent || '');
    var slug = uniqueSlug(slugify(stripEmoji(strong.textContent)) || ('item-' + idx));

    el.innerHTML = '';
    el.id = slug;
    el.classList.add('exec-card');
    if (risk) el.classList.add(risk.itemCls);

    var head = document.createElement('div');
    head.className = 'exec-card-head';

    var headText = document.createElement('span');
    headText.className = 'exec-card-head-text';
    headText.appendChild(headFrag);

    var anchor = document.createElement('a');
    anchor.href = '#' + slug;
    anchor.className = 'exec-card-anchor';
    anchor.title = 'Copy link to this item';
    anchor.textContent = '🔗';
    anchor.addEventListener('click', function (e) {
      e.stopPropagation();
      history.replaceState(null, '', '#' + slug);
      navigator.clipboard && navigator.clipboard.writeText(window.location.href);
    });

    var chevron = document.createElement('span');
    chevron.className = 'exec-card-chevron';
    chevron.setAttribute('aria-hidden', 'true');
    chevron.textContent = '›';

    head.appendChild(headText);
    head.appendChild(anchor);
    head.appendChild(chevron);

    var body = document.createElement('div');
    body.className = 'exec-card-body';
    body.appendChild(bodyFrag);

    el.appendChild(head);
    el.appendChild(body);

    head.addEventListener('click', function () {
      el.classList.toggle('exec-card-open');
    });
  }

  function cardify(body) {
    var els = [];
    body.querySelectorAll(':scope > ul > li').forEach(function (li) { els.push(li); });
    body.querySelectorAll(':scope > p').forEach(function (p) { els.push(p); });
    els.forEach(cardifyOne);
  }

  // Scroll progress bar — gives a sense of "almost done" on long pages.
  function updateProgressBar() {
    var bar = document.getElementById('exec-progress-bar');
    if (!bar) return;
    var doc = document.documentElement;
    var scrollTop = window.pageYOffset || doc.scrollTop;
    var height = doc.scrollHeight - doc.clientHeight;
    var pct = height > 0 ? Math.min(100, Math.max(0, (scrollTop / height) * 100)) : 0;
    bar.style.width = pct + '%';
  }

  // Surfaces the single highest-priority item above the fold — added
  // 2026-07-21 so an exec sees the week's biggest risk in the first few
  // seconds instead of reading down through six sections to find it.
  // Reuses whatever the FIRST high-risk element in reading order is (Week
  // at a Glance is always the first section, so its bullets win naturally).
  function buildHeroAlert(content) {
    var box = document.getElementById('exec-hero-alert');
    if (!box) return;
    var el = content.querySelector('.exec-card.exec-item-high, tr.exec-row-high');
    if (!el) return;

    // Cardified items (the normal 2026-07-21+ case) had their innerHTML
    // restructured into head/body divs by cardify() — rebuild the banner
    // text from those instead of the card's own innerHTML. Legacy table
    // rows (older exec guides) were never cardified, so fall back to their
    // raw innerHTML directly.
    var text;
    if (el.classList.contains('exec-card')) {
      var headText = el.querySelector('.exec-card-head-text');
      var bodyText = el.querySelector('.exec-card-body');
      text = (headText ? headText.innerHTML : '') + ' ' + (bodyText ? bodyText.innerHTML : '');
    } else {
      text = el.innerHTML || '';
    }
    text = text.split(RISK.HIGH.emoji).join('').trim();
    if (!text) return;
    box.innerHTML =
      '<div class="exec-hero-icon" aria-hidden="true">' + RISK.HIGH.emoji + '</div>' +
      '<div><div class="exec-hero-label">Highest priority this week</div>' +
      '<div class="exec-hero-text">' + text + '</div></div>';
    box.style.display = 'flex';
  }

  function styleSourceLines(body) {
    body.querySelectorAll('p').forEach(function (p) {
      var em = p.querySelector('em');
      if (!em) return;
      var t = em.textContent || '';
      if (t.indexOf('Sources') === -1 && t.indexOf('Source') === -1) return;
      if (p.children.length === 1 && p.firstElementChild.tagName === 'EM') {
        p.innerHTML = p.firstElementChild.innerHTML;
      }
      p.classList.add('exec-sources-block');
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var content  = document.getElementById('exec-content');
    var tocLinks = document.getElementById('exec-toc-links');
    if (!content || !tocLinks) return;

    var h2s = Array.from(content.querySelectorAll('h2'));
    if (!h2s.length) return;

    var allDetails = [];
    var firstMain  = true;

    h2s.forEach(function (h2, idx) {
      var label = h2.textContent || '';
      var slug  = h2.id || slugify(stripEmoji(label)) || ('section-' + idx);
      var risk  = detectRisk(label);

      // Collect sibling nodes until next h2
      var nodes = [];
      var node = h2.nextSibling;
      while (node && !(node.nodeType === 1 && node.tagName === 'H2')) {
        nodes.push(node);
        node = node.nextSibling;
      }

      var details = document.createElement('details');
      details.id = slug;
      details.open = firstMain;
      firstMain = false;
      details.className = 'exec-section-collapsible' + (risk ? ' ' + risk.cls : '');

      var summary = document.createElement('summary');
      summary.className = 'exec-section-summary' + (risk ? ' ' + risk.cls : '');
      summary.textContent = label;

      var anchor = document.createElement('a');
      anchor.href = '#' + slug;
      anchor.className = 'exec-section-anchor';
      anchor.title = 'Copy link to this section';
      anchor.textContent = '🔗';
      anchor.addEventListener('click', function (e) {
        e.stopPropagation();
        history.replaceState(null, '', '#' + slug);
        navigator.clipboard && navigator.clipboard.writeText(window.location.href);
      });
      summary.appendChild(anchor);

      var body = document.createElement('div');
      body.className = 'exec-section-body';
      nodes.forEach(function (n) { body.appendChild(n); });

      details.appendChild(summary);
      details.appendChild(body);
      h2.parentNode.replaceChild(details, h2);

      colorTableRows(body);
      cardify(body);
      styleSourceLines(body);
      allDetails.push(details);

      // TOC pill
      var pill = document.createElement('a');
      pill.href = '#' + slug;
      pill.className = 'exec-toc-pill' + (risk ? ' ' + risk.cls : '');
      pill.textContent = stripEmoji(label).replace(/\s*—.*$/, '').trim();
      pill.addEventListener('click', function (e) {
        e.preventDefault();
        details.open = true;
        details.scrollIntoView({ behavior: 'smooth', block: 'start' });
        history.replaceState(null, '', '#' + slug);
      });
      tocLinks.appendChild(pill);
    });

    // Expand / Collapse all
    var actions = document.createElement('div');
    actions.className = 'exec-toc-actions';
    var btnExpand = document.createElement('button');
    btnExpand.className = 'exec-toggle-btn';
    btnExpand.textContent = 'Expand all';
    btnExpand.addEventListener('click', function () { allDetails.forEach(function (d) { d.open = true; }); });
    var btnCollapse = document.createElement('button');
    btnCollapse.className = 'exec-toggle-btn';
    btnCollapse.textContent = 'Collapse all';
    btnCollapse.addEventListener('click', function () { allDetails.forEach(function (d) { d.open = false; }); });
    actions.appendChild(btnExpand);
    actions.appendChild(btnCollapse);
    document.getElementById('exec-toc').appendChild(actions);

    // Stat strip — count actual risk-flagged bullets/rows now that
    // colorTableRows/cardify have tagged them, rather than the old
    // per-section-title check (which never matched anything, since H2s
    // never contain emoji — only their bullets do). 2026-07-21.
    var riskCounts = {
      HIGH: content.querySelectorAll('.exec-item-high, .exec-row-high').length,
      MED:  content.querySelectorAll('.exec-item-med, .exec-row-med').length,
      LOW:  content.querySelectorAll('.exec-item-low, .exec-row-low').length,
    };
    var dashboard = document.getElementById('exec-risk-dashboard');
    if (dashboard) {
      [
        { key: 'HIGH', cls: 'exec-stat-card-high', label: 'High risk items' },
        { key: 'MED',  cls: 'exec-stat-card-med',  label: 'Medium risk items' },
        { key: 'LOW',  cls: 'exec-stat-card-low',  label: 'Low risk items' },
      ].forEach(function (c) {
        if (!riskCounts[c.key]) return;
        var card = document.createElement('div');
        card.className = 'exec-stat-card ' + c.cls;
        card.innerHTML = '<div class="exec-stat-number">' + riskCounts[c.key] + '</div>' +
          '<div class="exec-stat-label">' + c.label + '</div>';
        dashboard.appendChild(card);
      });
    }

    buildHeroAlert(content);

    // Auto-open hash target — handles both a whole section (<details>) and,
    // since cards are individually deep-linkable now, a single card inside
    // one (expand its parent section too, then scroll to the card itself).
    var hash = window.location.hash.slice(1);
    if (hash) {
      var target = document.getElementById(decodeURIComponent(hash));
      if (target && target.tagName === 'DETAILS') {
        target.open = true;
        setTimeout(function () { target.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 80);
      } else if (target && target.classList.contains('exec-card')) {
        target.classList.add('exec-card-open');
        var parentDetails = target.closest('details');
        if (parentDetails) parentDetails.open = true;
        setTimeout(function () { target.scrollIntoView({ behavior: 'smooth', block: 'center' }); }, 80);
      }
    }

    window.addEventListener('scroll', updateProgressBar);
    updateProgressBar();
  });
})();
