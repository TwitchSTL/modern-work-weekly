/**
 * exec-nav.js — Executive's Guide section navigation.
 *
 * 1. Finds all h2 headings inside .exec-content
 * 2. Wraps each section in a <details> for collapsible reading
 * 3. Builds a jump-to pill nav from those headings
 * 4. Auto-opens the section targeted by URL hash
 */

(function () {
  'use strict';

  // Emoji-to-label map for risk indicators in headings
  var RISK_CLASS = {
    '🔴': 'exec-risk-high',
    '🟡': 'exec-risk-med',
    '🟢': 'exec-risk-low',
  };

  function slugify(text) {
    return text.toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '')
      .trim()
      .replace(/\s+/g, '-');
  }

  function stripEmoji(text) {
    return text.replace(/[\u{1F300}-\u{1FAFF}]/gu, '').replace(/⚠️/g, '').trim();
  }

  function riskClass(text) {
    for (var emoji in RISK_CLASS) {
      if (text.indexOf(emoji) !== -1) return RISK_CLASS[emoji];
    }
    return '';
  }

  document.addEventListener('DOMContentLoaded', function () {
    var content = document.getElementById('exec-content');
    var tocLinks = document.getElementById('exec-toc-links');
    if (!content || !tocLinks) return;

    var h2s = Array.from(content.querySelectorAll('h2'));
    if (!h2s.length) return;

    // Build sections: each h2 + everything until the next h2 (or end)
    h2s.forEach(function (h2, idx) {
      var label = h2.textContent || '';
      var slug = h2.id || slugify(stripEmoji(label)) || ('section-' + idx);
      h2.id = slug;

      // Collect sibling nodes until next h2
      var nodes = [];
      var node = h2.nextSibling;
      while (node && !(node.nodeType === 1 && node.tagName === 'H2')) {
        nodes.push(node);
        node = node.nextSibling;
      }

      // Build <details> wrapper
      var details = document.createElement('details');
      details.className = 'exec-section-collapsible';
      details.id = slug;
      details.open = true; // open by default

      var risk = riskClass(label);

      var summary = document.createElement('summary');
      summary.className = 'exec-section-summary' + (risk ? ' ' + risk : '');
      summary.textContent = label;

      var body = document.createElement('div');
      body.className = 'exec-section-body';
      nodes.forEach(function (n) { body.appendChild(n); });

      details.appendChild(summary);
      details.appendChild(body);

      h2.parentNode.replaceChild(details, h2);

      // TOC pill
      var a = document.createElement('a');
      a.href = '#' + slug;
      a.className = 'exec-toc-pill' + (risk ? ' ' + risk : '');
      a.textContent = stripEmoji(label).replace(/\s*—.*$/, '').trim(); // short label
      a.addEventListener('click', function (e) {
        e.preventDefault();
        details.open = true;
        details.scrollIntoView({ behavior: 'smooth', block: 'start' });
        history.replaceState(null, '', '#' + slug);
      });
      tocLinks.appendChild(a);
    });

    // Auto-open hash target
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
