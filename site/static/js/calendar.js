/**
 * calendar.js — 30-day deadline calendar for the homepage sidebar.
 *
 * Reads deadline data from #deadline-calendar[data-deadlines],
 * renders a mini month grid with colored event dots,
 * and a clickable upcoming-deadlines list below.
 */

(function () {
  const PILLAR_COLORS = {
    'Identity':                '#a78bfa',
    'Devices':                 '#3fb950',
    'Apps':                    '#58a6ff',
    'Data':                    '#f0883e',
    'Network':                 '#39d353',
    'Visibility & Automation': '#d2a8ff',
  };

  function toLocal(dateStr) {
    // Parse "YYYY-MM-DD" as local midnight to avoid UTC-shift issues
    const [y, m, d] = dateStr.split('-').map(Number);
    const dt = new Date(y, m - 1, d);
    dt.setHours(0, 0, 0, 0);
    return dt;
  }

  function toKey(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  function buildMonthGrid(year, month, deadlineMap, today) {
    const firstDay  = new Date(year, month, 1);
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const monthName = firstDay.toLocaleString('default', { month: 'long', year: 'numeric' });

    let html = `<div class="cal-month">`;
    html += `<div class="cal-month-name">${monthName}</div>`;
    html += `<div class="cal-grid">`;

    // Day-of-week headers
    for (const h of ['S','M','T','W','T','F','S']) {
      html += `<div class="cal-dow">${h}</div>`;
    }

    // Leading empty cells
    for (let i = 0; i < firstDay.getDay(); i++) {
      html += `<div class="cal-day cal-day-empty"></div>`;
    }

    for (let d = 1; d <= daysInMonth; d++) {
      const date    = new Date(year, month, d);
      const dateStr = toKey(date);
      const isToday = dateStr === toKey(today);
      const isPast  = date < today && !isToday;
      const events  = deadlineMap[dateStr];

      const cls = [
        'cal-day',
        isToday          ? 'cal-today'      : '',
        isPast           ? 'cal-past'       : '',
        events           ? 'cal-has-events' : '',
      ].filter(Boolean).join(' ');

      let dots = '';
      if (events) {
        dots = '<div class="cal-dots">' +
          events.map(e =>
            `<span class="cal-dot" style="background:${PILLAR_COLORS[e.pillar] || '#6e7681'}" title="${e.title}"></span>`
          ).join('') + '</div>';
      }

      html += `<div class="${cls}" data-date="${dateStr}">${d}${dots}</div>`;
    }

    html += `</div></div>`;
    return html;
  }

  document.addEventListener('DOMContentLoaded', function () {
    const calEl    = document.getElementById('deadline-calendar');
    const listEl   = document.getElementById('deadline-upcoming');
    if (!calEl) return;

    const deadlines = JSON.parse(calEl.dataset.deadlines || '[]');

    const today  = new Date();
    today.setHours(0, 0, 0, 0);
    const cutoff = new Date(today);
    cutoff.setDate(cutoff.getDate() + 30);

    // Build date → deadlines map
    const deadlineMap = {};
    deadlines.forEach(function (d) {
      if (!deadlineMap[d.date]) deadlineMap[d.date] = [];
      deadlineMap[d.date].push(d);
    });

    // Build calendar grid(s) — current month, plus next if 30-day window crosses
    const thisYear  = today.getFullYear();
    const thisMonth = today.getMonth();
    let calHtml = buildMonthGrid(thisYear, thisMonth, deadlineMap, today);

    if (cutoff.getMonth() !== thisMonth || cutoff.getFullYear() !== thisYear) {
      calHtml += buildMonthGrid(cutoff.getFullYear(), cutoff.getMonth(), deadlineMap, today);
    }

    calEl.innerHTML = calHtml;

    // Upcoming list — deadlines in the next 30 days
    const upcoming = deadlines
      .map(function (d) { return { ...d, _date: toLocal(d.date) }; })
      .filter(function (d) { return d._date >= today && d._date <= cutoff; })
      .sort(function (a, b) { return a._date - b._date; });

    if (listEl) {
      if (upcoming.length === 0) {
        listEl.innerHTML = '<p class="sidebar-empty">No deadlines in the next 30 days</p>';
      } else {
        const items = upcoming.map(function (d) {
          const diff  = Math.round((d._date - today) / 86400000);
          const color = PILLAR_COLORS[d.pillar] || '#6e7681';

          let urgencyLabel = '';
          let urgencyClass = '';
          if (diff === 0)        { urgencyLabel = ' — TODAY';      urgencyClass = 'is-urgent'; }
          else if (diff <= 14)   { urgencyLabel = ` — ${diff}d`;   urgencyClass = 'is-urgent'; }
          else if (diff <= 30)   { urgencyLabel = ` — ${diff}d`;   urgencyClass = 'is-soon';   }

          return `
<div class="cal-upcoming-item ${urgencyClass}" data-date="${d.date}" style="border-left-color:${color}">
  <div class="cal-upcoming-date">${d.date}${urgencyLabel}</div>
  <div class="cal-upcoming-title">${d.title}</div>
  <div class="cal-upcoming-pillar" style="color:${color}">${d.pillar}</div>
  <div class="cal-upcoming-action">${d.action}</div>
</div>`;
        }).join('');

        listEl.innerHTML = `<div class="cal-upcoming">${items}</div>`;
      }
    }

    // Clicking a day with events scrolls/highlights its list item
    calEl.querySelectorAll('.cal-day.cal-has-events').forEach(function (cell) {
      cell.addEventListener('click', function () {
        const dateStr = this.dataset.date;
        if (!listEl) return;

        // Toggle highlight on matching list item
        listEl.querySelectorAll('.cal-upcoming-item').forEach(function (item) {
          const match = item.dataset.date === dateStr;
          item.classList.toggle('cal-highlighted', match);
        });

        // Scroll the first match into view
        const match = listEl.querySelector(`.cal-upcoming-item[data-date="${dateStr}"]`);
        if (match) match.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      });
    });
  });
})();
