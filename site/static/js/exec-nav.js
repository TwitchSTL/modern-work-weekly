/**
 * exec-nav.js — Executive's Guide section navigation and UX enhancements.
 *
 * 1. Extracts Planning Horizon, If You Take No Action, Help Desk, and Cost &
 *    Licensing into color-coded sidebar panels (Help Desk becomes a checklist)
 * 2. Wraps remaining h2 sections in collapsible <details> cards with risk-color coding
 * 3. Builds a jump-to pill nav (sidebar sections excluded) with expand/collapse all
 * 4. Builds a risk dashboard (HIGH / MED / LOW counts)
 * 5. Color-codes table rows containing risk emojis
 * 6. Adds anchor share links to each section header
 * 7. Styles source citation lines as a distinct block
 * 8. Auto-opens section targeted by URL hash
 */

(function () {
  'use strict';

  var RISK = {
    HIGH: { emoji: '🔴', cls: 'exec-risk-high', rowCls: 'exec-row-high', label: 'High' },
    MED:  { emoji: '🟡', cls: 'exec-risk-med',  rowCls: 'exec-row-med',  label: 'Medium' },
    LOW:  { emoji: '🟢', cls: 'exec-risk-low',  rowCls: 'exec-row-low',  label: 'Low' },
  };

  // Sections to extract to the sidebar instead of rendering as collapsibles.
  // Matched against the lowercased h2 text content.
  var SIDEBAR_SECTIONS = [
    {
      match: 'planning horizon',
      label: 'Planning Horizon',
      color: '#58a6ff',
      bg: 'rgba(88,166,255,0.08)',
      border: 'rgba(88,166,255,0.25)',
      checklist: false,
      emptyMsg: null
    },
    {
      match: 'if you take no action',
      label: 'If You Take No Action',
      color: '#ff6b6b',
      bg: 'rgba(255,107,107,0.08)',
      border: 'rgba(255,107,107,0.25)',
      checklist: false,
      emptyMsg: null
    },
    {
      match: 'what your help desk should expect',
      label: 'Help Desk Checklist',
      color: '#f0883e',
      bg: 'rgba(240,136,62,0.08)',
      border: 'rgba(240,136,62,0.25)',
      checklist: true,
      emptyMsg: null
    },
    {
      match: 'cost & licensing',
      label: 'Cost & Licensing',
      color: '#a78bfa',
      bg: 'rgba(167,139,250,0.08)',
      border: 'rgba(167,139,250,0.25)',
      checklist: false,
      emptyMsg: 'No cost or licensing updates this week.'
    }
  ];

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

  function getSidebarConfig(label) {
    var lower = (label || '').toLowerCase();
    for (var i = 0; i < SIDEBAR_SECTIONS.length; i++) {
      if (lower.indexOf(SIDEBAR_SECTIONS[i].match) !== -1) return SIDEBAR_SECTIONS[i];
    }
    return null;
  }

  function convertToChecklist(body) {
    var items = body.querySelectorAll('li');
    if (!items.length) return;
    var list = document.createElement('div');
    list.className = 'exec-checklist';
    items.forEach(function (li) {
      var item = document.createElement('label');
      item.className = 'exec-checklist-item';
      var cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.className = 'exec-checklist-cb';
      var span = document.createElement('span');
      span.innerHTML = li.innerHTML;
      item.appendChild(cb);
      item.appendChild(span);
      list.appendChild(item);
    });
    body.querySelectorAll('ul, ol').forEach(function (ul) {
      if (ul.parentNode) ul.parentNode.removeChild(ul);
    });
    body.appendChild(list);
  }

  function buildSidebarPanel(config, nodes) {
    var panel = document.createElement('div');
    panel.className = 'exec-sidebar-panel';
    panel.style.borderLeftColor = config.color;

    var header = document.createElement('div');
    header.className = 'exec-sidebar-panel-header';
    header.style.color = config.color;
    header.style.borderBottomColor = config.border;
    header.style.background = config.bg;
    header.textContent = config.label.toUpperCase();
    panel.appendChild(header);

    var body = document.createElement('div');
    body.className = 'exec-sidebar-panel-body';
    nodes.forEach(function (n) { body.appendChild(n.cloneNode(true)); });

    var text = body.textContent.trim();
    if (!text && config.emptyMsg) {
      var empty = document.createElement('p');
      empty.className = 'exec-sidebar-empty';
      empty.textContent = config.emptyMsg;
      body.appendChild(empty);
    }

    if (config.checklist) convertToChecklist(body);
    styleSourceLines(body);
    colorTableRows(body);

    panel.appendChild(body);
    return panel;
  }

  document.addEventListener('DOMContentLoaded', function () {
    var content  = document.getElementById('exec-content');
    var tocLinks = document.getElementById('exec-toc-links');
    var sidebar  = document.getElementById('exec-sidebar');
    if (!content || !tocLinks) return;

    var h2s = Array.from(content.querySelectorAll('h2'));
    if (!h2s.length) return;

    var allDetails    = [];
    var riskCounts    = { HIGH: 0, MED: 0, LOW: 0 };
    var sidebarPanels = [];
    var firstMain     = true;

    h2s.forEach(function (h2, idx) {
      var label = h2.textContent || '';
      var slug  = h2.id || slugify(stripEmoji(label)) || ('section-' + idx);
      var risk  = detectRisk(label);
      var sidebarConfig = getSidebarConfig(label);

      // Collect sibling nodes until next h2
      var nodes = [];
      var node = h2.nextSibling;
      while (node && !(node.nodeType === 1 && node.tagName === 'H2')) {
        nodes.push(node);
        node = node.nextSibling;
      }

      if (sidebarConfig) {
        // ── Sidebar section ──────────────────────────────────────────────
        sidebarPanels.push(buildSidebarPanel(sidebarConfig, nodes));
        nodes.forEach(function (n) { if (n.parentNode) n.parentNode.removeChild(n); });
        if (h2.parentNode) h2.parentNode.removeChild(h2);
        return;
      }

      // ── Main collapsible section ─────────────────────────────────────
      if (risk) riskCounts[risk.label === 'High' ? 'HIGH' : risk.label === 'Medium' ? 'MED' : 'LOW']++;

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

    // ── Expand / Collapse all ────────────────────────────────────────────
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

    // ── Risk dashboard ───────────────────────────────────────────────────
    var dashboard = document.getElementById('exec-risk-dashboard');
    if (dashboard) {
      [
        { key: 'HIGH', cls: 'exec-risk-chip-high', label: 'High' },
        { key: 'MED',  cls: 'exec-risk-chip-med',  label: 'Medium' },
        { key: 'LOW',  cls: 'exec-risk-chip-low',  label: 'Low' },
      ].forEach(function (c) {
        if (!riskCounts[c.key]) return;
        var chip = document.createElement('span');
        chip.className = 'exec-risk-chip ' + c.cls;
        chip.innerHTML = '<span class="exec-risk-chip-count">' + riskCounts[c.key] + '</span> ' + c.label;
        dashboard.appendChild(chip);
      });
    }

    // ── Inject sidebar panels before health/deadlines partials ──────────
    if (sidebar && sidebarPanels.length) {
      var ref = sidebar.firstChild;
      sidebarPanels.forEach(function (panel) {
        sidebar.insertBefore(panel, ref);
      });
    }

    // ── Auto-open hash target ────────────────────────────────────────────
    var hash = window.location.hash.slice(1);
    if (hash) {
      var target = document.getElementById(decodeURIComponent(hash));
      if (target && target.tagName === 'DETAILS') {
        target.open = true;
        setTimeout(function () { target.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 80);
      }
    }
  });
})();
