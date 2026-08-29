/**
 * review-tray.js — Lets a site visitor (an exec) check off individual
 * articles while browsing digests, then send the picked list to someone
 * via Outlook Web, a plain mailto: link, or a Teams chat deep link.
 *
 * Everything here is client-side only. This is a static Hugo site with no
 * backend, so the "send" step is always: build a plain-text message, then
 * hand it to the visitor's own email/Teams client to actually send. Nothing
 * leaves the browser automatically — every send button opens an external
 * app/tab pre-filled and stops there. That's called out in the tray UI
 * itself so visitors don't wonder what's happening on their machine.
 *
 * Selections persist in localStorage so an exec can check items on this
 * week's digest, then last week's, then send one combined list.
 *
 * Item identity: the article's own URL (the href already extracted from
 * the bullet's bold title). No new IDs are added to markdown/posts — this
 * reads the DOM Hugo already renders, so it works on every past and future
 * digest post with zero changes to the content pipeline (forward- and
 * backward-compatible, unlike a scheme that required tagging posts).
 */
(function () {
  var STORAGE_KEY = 'mww-review-tray-items';
  var NOTE_KEY = 'mww-review-tray-note';
  var RECIPIENT_KEY = 'mww-review-tray-recipient';
  var OPEN_KEY = 'mww-review-tray-open';

  /* ── Storage helpers (all wrapped — localStorage can throw or be absent) ── */

  function safeGet(key) {
    try { return window.localStorage.getItem(key); } catch (e) { return null; }
  }
  function safeSet(key, val) {
    try { window.localStorage.setItem(key, val); } catch (e) { /* ignore */ }
  }

  function loadItems() {
    var raw = safeGet(STORAGE_KEY);
    if (!raw) return [];
    try {
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  function saveItems(items) {
    safeSet(STORAGE_KEY, JSON.stringify(items));
  }

  function isInTray(items, url) {
    return items.some(function (it) { return it.url === url; });
  }

  /* ── DOM: inject a checkbox next to every checkable item ──────────────
     A "checkable" item is any <li> whose bold title is itself a link —
     i.e. the standard "- **[Title](url)** `Tag` — description" bullet
     format used under every category / Documentation Updates section, on
     both the technical digest and the Executive's Guide. Top 5 entries
     are summaries, not individual sourced items, and are skipped since
     most don't carry their own single link. */

  function findCheckableItems(root) {
    return Array.from(root.querySelectorAll('li')).filter(function (li) {
      if (li.dataset.reviewInjected) return false;
      var strong = li.querySelector('strong');
      if (!strong) return false;
      var a = strong.querySelector('a[href]');
      return !!a;
    });
  }

  function injectCheckboxes(root, items) {
    findCheckableItems(root).forEach(function (li) {
      var strong = li.querySelector('strong');
      var a = strong.querySelector('a[href]');
      var url = a.href;
      var title = a.textContent.trim();

      li.dataset.reviewInjected = 'true';
      li.classList.add('review-tray-host');

      var label = document.createElement('label');
      label.className = 'review-check-wrap';
      label.title = 'Add to review list';

      var cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.className = 'review-check';
      cb.checked = isInTray(items, url);
      if (cb.checked) li.classList.add('review-checked');

      cb.addEventListener('change', function () {
        var current = loadItems();
        if (cb.checked) {
          if (!isInTray(current, url)) {
            current.push({ title: title, url: url, added: Date.now() });
          }
        } else {
          current = current.filter(function (it) { return it.url !== url; });
        }
        saveItems(current);
        li.classList.toggle('review-checked', cb.checked);
        renderTray(current);
      });

      label.appendChild(cb);
      li.insertBefore(label, li.firstChild);
    });
  }

  /* ── Floating tray widget ──────────────────────────────────────────── */

  var els = {};

  function buildTrayShell() {
    var root = document.createElement('div');
    root.id = 'review-tray-root';
    root.innerHTML =
      '<button type="button" id="review-tray-toggle" class="review-tray-toggle">' +
        '<span id="review-tray-count">0</span> selected — Review &amp; send' +
      '</button>' +
      '<div id="review-tray-panel" class="review-tray-panel">' +
        '<div class="review-tray-header">' +
          '<span>Review list</span>' +
          '<button type="button" id="review-tray-close" class="review-tray-icon-btn" aria-label="Close">&times;</button>' +
        '</div>' +
        '<div id="review-tray-list" class="review-tray-list"></div>' +
        '<div class="review-tray-empty" id="review-tray-empty">No items selected yet — check the box next to any article title to add it here.</div>' +
        '<textarea id="review-tray-note" class="review-tray-note" placeholder="Add a note (optional) — this goes at the top of the message" rows="2"></textarea>' +
        '<input id="review-tray-recipient" class="review-tray-recipient" type="text" placeholder="Recipient email (optional — you can also fill this in after it opens)">' +
        '<div class="review-tray-actions">' +
          '<button type="button" id="review-tray-outlook" class="review-tray-btn review-tray-btn-primary">Open in Outlook Web</button>' +
          '<button type="button" id="review-tray-mailto" class="review-tray-btn">Email (default app)</button>' +
          '<button type="button" id="review-tray-teams" class="review-tray-btn">Open in Teams</button>' +
        '</div>' +
        '<div class="review-tray-disclosure">Opens with a pre-filled subject and message — nothing is sent automatically. You review and hit send yourself in Outlook, Teams, or your email app.</div>' +
        '<button type="button" id="review-tray-clear" class="review-tray-clear">Clear list</button>' +
      '</div>';
    document.body.appendChild(root);

    els.root = root;
    els.toggle = root.querySelector('#review-tray-toggle');
    els.panel = root.querySelector('#review-tray-panel');
    els.close = root.querySelector('#review-tray-close');
    els.count = root.querySelector('#review-tray-count');
    els.list = root.querySelector('#review-tray-list');
    els.empty = root.querySelector('#review-tray-empty');
    els.note = root.querySelector('#review-tray-note');
    els.recipient = root.querySelector('#review-tray-recipient');
    els.clear = root.querySelector('#review-tray-clear');

    els.note.value = safeGet(NOTE_KEY) || '';
    els.recipient.value = safeGet(RECIPIENT_KEY) || '';

    els.note.addEventListener('input', function () { safeSet(NOTE_KEY, els.note.value); });
    els.recipient.addEventListener('input', function () { safeSet(RECIPIENT_KEY, els.recipient.value); });

    els.toggle.addEventListener('click', function () { setPanelOpen(true); });
    els.close.addEventListener('click', function () { setPanelOpen(false); });

    els.clear.addEventListener('click', function () {
      saveItems([]);
      // Uncheck any boxes visible on the current page.
      document.querySelectorAll('.review-check:checked').forEach(function (cb) {
        cb.checked = false;
        var li = cb.closest('li');
        if (li) li.classList.remove('review-checked');
      });
      renderTray([]);
    });

    els.root.querySelector('#review-tray-outlook').addEventListener('click', function () { sendVia('outlook'); });
    els.root.querySelector('#review-tray-mailto').addEventListener('click', function () { sendVia('mailto'); });
    els.root.querySelector('#review-tray-teams').addEventListener('click', function () { sendVia('teams'); });

    if (safeGet(OPEN_KEY) === 'true') setPanelOpen(true);
  }

  function setPanelOpen(open) {
    els.panel.classList.toggle('is-open', open);
    safeSet(OPEN_KEY, open ? 'true' : 'false');
  }

  function renderTray(items) {
    els.count.textContent = String(items.length);
    els.root.classList.toggle('has-items', items.length > 0);
    els.list.innerHTML = '';

    if (items.length === 0) {
      els.empty.style.display = 'block';
    } else {
      els.empty.style.display = 'none';
      items.forEach(function (it) {
        var row = document.createElement('div');
        row.className = 'review-tray-row';

        var link = document.createElement('a');
        link.href = it.url;
        link.target = '_blank';
        link.rel = 'noopener';
        link.textContent = it.title;
        link.className = 'review-tray-row-title';

        var remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'review-tray-icon-btn';
        remove.setAttribute('aria-label', 'Remove');
        remove.innerHTML = '&times;';
        remove.addEventListener('click', function () {
          var next = loadItems().filter(function (x) { return x.url !== it.url; });
          saveItems(next);
          renderTray(next);
          // Uncheck the box if this item's post is the one currently on screen.
          document.querySelectorAll('.review-check:checked').forEach(function (cb) {
            var li = cb.closest('li');
            var a = li && li.querySelector('strong a[href]');
            if (a && a.href === it.url) {
              cb.checked = false;
              li.classList.remove('review-checked');
            }
          });
        });

        row.appendChild(link);
        row.appendChild(remove);
        els.list.appendChild(row);
      });
    }
  }

  /* ── Message building + the three send paths ──────────────────────── */

  function buildMessage(items) {
    var note = (els.note.value || '').trim();
    var subject = 'Modern Work Weekly — ' + items.length + ' item' + (items.length === 1 ? '' : 's') + ' for review';

    var lines = [];
    if (note) { lines.push(note); lines.push(''); }
    lines.push('Items for review:');
    items.forEach(function (it, i) {
      lines.push((i + 1) + '. ' + it.title);
      lines.push('   ' + it.url);
    });
    lines.push('');
    lines.push('Sent via Modern Work Weekly (modernworkweekly.com)');

    return { subject: subject, body: lines.join('\n') };
  }

  function sendVia(channel) {
    var items = loadItems();
    if (items.length === 0) return;

    var msg = buildMessage(items);
    var to = (els.recipient.value || '').trim();

    if (channel === 'outlook') {
      var url = 'https://outlook.office.com/mail/deeplink/compose'
        + '?to=' + encodeURIComponent(to)
        + '&subject=' + encodeURIComponent(msg.subject)
        + '&body=' + encodeURIComponent(msg.body);
      window.open(url, '_blank', 'noopener');
    } else if (channel === 'mailto') {
      var mailto = 'mailto:' + encodeURIComponent(to).replace(/%40/g, '@')
        + '?subject=' + encodeURIComponent(msg.subject)
        + '&body=' + encodeURIComponent(msg.body);
      window.location.href = mailto;
    } else if (channel === 'teams') {
      var teamsUrl = 'https://teams.microsoft.com/l/chat/0/0'
        + '?users=' + encodeURIComponent(to)
        + '&message=' + encodeURIComponent(msg.subject + '\n\n' + msg.body);
      window.open(teamsUrl, '_blank', 'noopener');
    }
  }

  /* ── Init ───────────────────────────────────────────────────────────── */

  document.addEventListener('DOMContentLoaded', function () {
    var content = document.querySelector('.post-content');
    var items = loadItems();

    buildTrayShell();
    renderTray(items);

    if (content) injectCheckboxes(content, items);
  });
})();
