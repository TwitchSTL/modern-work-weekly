/**
 * sidebar-dates.js — Classifies deadline items by proximity to today.
 * Adds is-overdue / is-urgent / is-soon CSS classes to .deadline-item[data-date].
 */
document.addEventListener('DOMContentLoaded', function () {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  document.querySelectorAll('.deadline-item[data-date]').forEach(function (item) {
    const parts = item.dataset.date.split('-').map(Number);
    // Use UTC noon to avoid timezone edge cases
    const d = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2], 12));
    const diff = Math.round((d - today) / 86400000);

    if (diff < 0) {
      item.classList.add('is-overdue');
      item.querySelector('.deadline-date').title = 'Passed';
    } else if (diff === 0) {
      item.classList.add('is-urgent');
      item.querySelector('.deadline-date').textContent += ' — TODAY';
    } else if (diff <= 14) {
      item.classList.add('is-urgent');
      item.querySelector('.deadline-date').textContent += ' — ' + diff + 'd';
    } else if (diff <= 30) {
      item.classList.add('is-soon');
      item.querySelector('.deadline-date').textContent += ' — ' + diff + 'd';
    }
  });
});
