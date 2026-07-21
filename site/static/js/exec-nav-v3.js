/**
 * exec-nav.js — Executive's Guide section navigation and UX enhancements.
 *
 * 1. Wraps h2 sections in collapsible <details> cards with risk-color coding
 * 2. Builds a jump-to pill nav with expand/collapse all
 * 3. Builds a risk dashboard (HIGH / MED / LOW counts)
 * 4. Color-codes table rows and list items containing risk emojis
 * 5. Adds anchor share links to each section header
 * 6. Styles source citation lines as a distinct block
 * 7. Auto-opens section targeted by URL hash
 * 8. Surfaces the single highest-priority item as a hero alert above the fold
 * 9. Drives a thin scroll-progress bar fixed to the top of the viewport
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

  // Risk & Compliance / Planning Horizon moved from tables to bulleted lists
  // 2026-07-21 — same idea as colorTableRows, but for <li> elements.
  function colorListItems(container) {
    container.querySelectorAll('li').forEach(function (li) {
      var text = li.textContent || '';
      var risk = detectRisk(text);
      if (risk) li.classList.add(risk.itemCls);
    });
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
    var el = content.querySelector('li.exec-item-high, tr.exec-row-high');
    if (!el) return;
    var text = (el.innerHTML || '').split(RISK.HIGH.emoji).join('').trim();
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
      colorListItems(body);
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
    // colorTableRows/colorListItems have tagged them, rather than the old
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

    // Auto-open hash target
    var hash = window.location.hash.slice(1);
    if (hash) {
      var target = document.getElementById(decodeURIComponent(hash));
      if (target && target.tagName === 'DETAILS') {
        target.open = true;
        setTimeout(function () { target.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 80);
      }
    }

    window.addEventListener('scroll', updateProgressBar);
    updateProgressBar();
  });
})();
