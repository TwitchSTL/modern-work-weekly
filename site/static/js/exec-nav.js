/**
 * exec-nav.js — Executive's Guide section navigation and UX enhancements.
 *
 * 1. Wraps each h2 section in a <details> card with risk-color coding
 * 2. Builds a jump-to pill nav with expand/collapse all controls
 * 3. Builds a risk dashboard (HIGH / MED / LOW counts)
 * 4. Color-codes table rows containing risk emojis
 * 5. Adds anchor share links to each section header
 * 6. Styles source citation lines as a distinct block
 * 7. Auto-opens section targeted by URL hash
 */

(function () {
  'use strict';

  var RISK = {
    HIGH: { emoji: '🔴', cls: 'exec-risk-high', rowCls: 'exec-row-high', label: 'High' },
    MED:  { emoji: '🟡', cls: 'exec-risk-med',  rowCls: 'exec-row-med',  label: 'Medium' },
    LOW:  { emoji: '🟢', cls: 'exec-risk-low',  rowCls: 'exec-row-low',  label: 'Low' },
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

  // Color table rows that contain risk emojis in any cell
  function colorTableRows(container) {
    container.querySelectorAll('table tr').forEach(function (tr) {
      var text = tr.textContent || '';
      var risk = detectRisk(text);
      if (risk) tr.classList.add(risk.rowCls);
    });
  }

  // Detect and style source citation lines (*Sources: ...*)
  function styleSourceLines(body) {
    var paras = body.querySelectorAll('p');
    paras.forEach(function (p) {
      var em = p.querySelector('em');
      if (!em) return;
      var t = em.textContent || '';
      if (t.indexOf('Sources') === -1 && t.indexOf('Source') === -1) return;
      p.classList.add('exec-sources-block');
      p.innerHTML = p.innerHTML; // preserve links
      // Remove the wrapping <em> but keep content
      if (p.children.length === 1 && p.firstElementChild.tagName === 'EM') {
        p.innerHTML = p.firstElementChild.innerHTML;
      }
      p.classList.add('exec-sources-block');
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var content = document.getElementById('exec-content');
    var tocLinks = document.getElementById('exec-toc-links');
    if (!content || !tocLinks) return;

    var h2s = Array.from(content.querySelectorAll('h2'));
    if (!h2s.length) return;

    var allDetails = [];
    var riskCounts = { HIGH: 0, MED: 0, LOW: 0 };

    // ── Build collapsible sections ────────────────────────────────────────
    h2s.forEach(function (h2, idx) {
      var label = h2.textContent || '';
      var slug = h2.id || slugify(stripEmoji(label)) || ('section-' + idx);
      var risk = detectRisk(label);
      var isFirst = (idx === 0);

      if (risk) riskCounts[risk.label === 'High' ? 'HIGH' : risk.label === 'Medium' ? 'MED' : 'LOW']++;

      // Collect sibling nodes until next h2
      var nodes = [];
      var node = h2.nextSibling;
      while (node && !(node.nodeType === 1 && node.tagName === 'H2')) {
        nodes.push(node);
        node = node.nextSibling;
      }

      // Build <details>
      var details = document.createElement('details');
      details.id = slug;
      details.open = isFirst;
      details.className = 'exec-section-collapsible' + (risk ? ' ' + risk.cls : '');

      // Summary with anchor link
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

      // Body
      var body = document.createElement('div');
      body.className = 'exec-section-body';
      nodes.forEach(function (n) { body.appendChild(n); });

      details.appendChild(summary);
      details.appendChild(body);

      h2.parentNode.replaceChild(details, h2);

      colorTableRows(body);
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

    // ── Expand / Collapse all buttons ─────────────────────────────────────
    var actions = document.createElement('div');
    actions.className = 'exec-toc-actions';

    var btnExpand = document.createElement('button');
    btnExpand.className = 'exec-toggle-btn';
    btnExpand.textContent = 'Expand all';
    btnExpand.addEventListener('click', function () {
      allDetails.forEach(function (d) { d.open = true; });
    });

    var btnCollapse = document.createElement('button');
    btnCollapse.className = 'exec-toggle-btn';
    btnCollapse.textContent = 'Collapse all';
    btnCollapse.addEventListener('click', function () {
      allDetails.forEach(function (d) { d.open = false; });
    });

    actions.appendChild(btnExpand);
    actions.appendChild(btnCollapse);
    document.getElementById('exec-toc').appendChild(actions);

    // ── Risk dashboard ─────────────────────────────────────────────────────
    var dashboard = document.getElementById('exec-risk-dashboard');
    if (dashboard) {
      var chips = [
        { key: 'HIGH', emoji: '🔴', cls: 'exec-risk-chip-high', label: 'High' },
        { key: 'MED',  emoji: '🟡', cls: 'exec-risk-chip-med',  label: 'Medium' },
        { key: 'LOW',  emoji: '🟢', cls: 'exec-risk-chip-low',  label: 'Low' },
      ];
      chips.forEach(function (c) {
        if (!riskCounts[c.key]) return;
        var chip = document.createElement('span');
        chip.className = 'exec-risk-chip ' + c.cls;
        chip.innerHTML = '<span class="exec-risk-chip-count">' + riskCounts[c.key] + '</span> ' + c.label;
        dashboard.appendChild(chip);
      });
    }

    // ── Auto-open hash target ──────────────────────────────────────────────
    var hash = window.location.hash.slice(1);
    if (hash) {
      var target = document.getElementById(decodeURIComponent(hash));
      if (target && target.tagName === 'DETAILS') {
        target.open = true;
        setTimeout(function () {
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 80);
      }
    }
  });
})();
