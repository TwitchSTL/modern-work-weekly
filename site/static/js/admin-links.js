/**
 * admin-links.js — Portals dropdown and private-mode launch helpers.
 *
 * togglePortals()            — open/close the nav dropdown
 * adminLaunchPrivate(url, mode) — copies URL + shows toast directing
 *   user to paste in Chrome Incognito (Ctrl+Shift+N) or Edge InPrivate
 *   (Ctrl+Shift+P). The microsoft-edge:?inprivate protocol is
 *   unreliable across Edge versions, so clipboard is used for both.
 */

// ── Dropdown toggle ──────────────────────────────────────────────────────────

function togglePortals() {
  var panel = document.getElementById('portals-panel');
  var btn   = document.querySelector('.portals-toggle');
  var caret = btn && btn.querySelector('.portals-caret');
  if (!panel) return;

  var opening = panel.hidden;
  panel.hidden = !opening;
  if (btn) btn.setAttribute('aria-expanded', opening ? 'true' : 'false');
  if (caret) caret.textContent = opening ? '▴' : '▾';
}

// Close when clicking anywhere outside the dropdown
document.addEventListener('click', function (e) {
  var dropdown = document.getElementById('portals-dropdown');
  if (!dropdown || dropdown.contains(e.target)) return;

  var panel = document.getElementById('portals-panel');
  var btn   = document.querySelector('.portals-toggle');
  var caret = btn && btn.querySelector('.portals-caret');
  if (panel && !panel.hidden) {
    panel.hidden = true;
    if (btn)   btn.setAttribute('aria-expanded', 'false');
    if (caret) caret.textContent = '▾';
  }
});

// Close on Escape key
document.addEventListener('keydown', function (e) {
  if (e.key !== 'Escape') return;
  var panel = document.getElementById('portals-panel');
  var btn   = document.querySelector('.portals-toggle');
  var caret = btn && btn.querySelector('.portals-caret');
  if (panel && !panel.hidden) {
    panel.hidden = true;
    if (btn)   btn.setAttribute('aria-expanded', 'false');
    if (caret) caret.textContent = '▾';
    if (btn)   btn.focus();
  }
});

// ── Private-mode launch ──────────────────────────────────────────────────────

function adminLaunchPrivate(url, mode) {
  var label = mode === 'incognito'
    ? 'Chrome Incognito (Ctrl+Shift+N)'
    : 'Edge InPrivate (Ctrl+Shift+P)';

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(url).then(function () {
      showAdminToast('URL copied — open ' + label + ' and paste');
    }).catch(function () {
      window.open(url, '_blank', 'noopener,noreferrer');
      showAdminToast('Opened in new tab — switch to ' + label);
    });
  } else {
    window.open(url, '_blank', 'noopener,noreferrer');
    showAdminToast('Opened in new tab — use ' + label + ' for your admin account');
  }
}

// ── Toast ────────────────────────────────────────────────────────────────────

function showAdminToast(msg) {
  var toast = document.getElementById('admin-toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add('admin-toast-visible');
  clearTimeout(toast._hideTimer);
  toast._hideTimer = setTimeout(function () {
    toast.classList.remove('admin-toast-visible');
  }, 3500);
}
