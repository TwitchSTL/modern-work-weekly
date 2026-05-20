/**
 * admin-links.js — Quick-launch portal buttons.
 *
 * adminLaunchIncognito(url):
 *   Copies the URL to the clipboard and shows a toast directing the user
 *   to paste it into a new Chrome Incognito window (Ctrl+Shift+N).
 *   Chrome has no URL protocol to force Incognito — clipboard is the
 *   closest reliable workaround.
 *
 * Edge InPrivate links use the microsoft-edge:?inprivate&url= protocol
 * directly in the href — no JS needed for those.
 */

function adminLaunchIncognito(url) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(url).then(function () {
      showAdminToast('URL copied — open Incognito (Ctrl+Shift+N) and paste');
    }).catch(function () {
      // Clipboard blocked (e.g. non-HTTPS dev environment) — fall back to new tab
      window.open(url, '_blank', 'noopener,noreferrer');
      showAdminToast('Opened in new tab — switch to Incognito for your admin account');
    });
  } else {
    // Old browser / no clipboard API
    window.open(url, '_blank', 'noopener,noreferrer');
    showAdminToast('Opened in new tab — use Incognito for your admin account');
  }
}

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
