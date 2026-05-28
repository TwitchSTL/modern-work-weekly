/**
 * admin-links.js — Portals dropdown and private-mode launch helpers.
 *
 * togglePortals()         — open/close the nav dropdown
 * adminLaunchPrivate(url) — copies URL to clipboard so the user can paste
 *   into whichever private/incognito window they open (Ctrl+Shift+N).
 *   Opening a specific browser's private mode from a web page is not
 *   reliably possible — clipboard-paste is the only cross-browser approach.
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

function adminLaunchPrivate(url) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(url).then(function () {
      showAdminToast('URL copied — press Ctrl+Shift+N to open a private window, then paste');
    }).catch(function () {
      window.open(url, '_blank', 'noopener,noreferrer');
      showAdminToast('Opened in new tab — use Ctrl+Shift+N for a private window with your admin account');
    });
  } else {
    window.open(url, '_blank', 'noopener,noreferrer');
    showAdminToast('Opened in new tab — use Ctrl+Shift+N for a private window with your admin account');
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
