/**
 * calendar.js — Deadline calendar for the homepage sidebar.
 *
 * Renders a rolling 5-week grid starting from today's week (no month boundaries),
 * plus an upcoming-deadlines list (next 3) below.
 */

(function () {
  const WEEKS_TO_SHOW = 5; // today's week + 4 more

  const PILLAR_COLORS = {
    'Identity':                '#a78bfa',
    'Devices':                 '#3fb950',
    'Apps':                    '#58a6ff',
    'Data':                    '#f0883e',
    'Network':                 '#39d353',
    'Visibility & Automation': '#d2a8ff',
  };

  function toLocal(dateStr) {
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

  /**
   * Builds a rolling week-based grid — no month boundaries, continuous days.
   * Starts from Sunday of today's week, runs for WEEKS_TO_SHOW weeks.
   * Past days in the current week are blanked out.
   */
  function buildWeekGrid(today, numWeeks, deadlineMap) {
    // Sunday of the week containing today
    const gridStart = new Date(today);
    gridStart.setDate(today.getDate() - today.getDay());
    gridStart.setHours(0, 0, 0, 0);

    // Last day in the grid
    const gridEnd = new Date(gridStart);
    gridEnd.setDate(gridStart.getDate() + numWeeks * 7 - 1);

    // Header: date range label
    const fmt     = { month: 'short', day: 'numeric' };
    const fmtYear = { month: 'short', day: 'numeric', year: 'numeric' };
    const startLabel = gridStart.toLocaleString('default', fmt);
    const endLabel   = gridEnd.toLocaleString('default', fmtYear);

    let html = '<div class="cal-month">';
    html += `<div class="cal-month-name">${startLabel} – ${endLabel}</div>`;
    html += '<div class="cal-grid">';

    for (const h of ['S', 'M', 'T', 'W', 'T', 'F', 'S']) {
      html += `<div class="cal-dow">${h}</div>`;
    }

    for (let i = 0; i < numWeeks * 7; i++) {
      const date = new Date(gridStart);
      date.setDate(gridStart.getDate() + i);
      date.setHours(0, 0, 0, 0);

      const dateStr = toKey(date);
      const isToday = dateStr === toKey(today);
      const isPast  = date < today && !isToday;

      // Blank past days so the grid reads left-to-right from today
      if (isPast) {
        html += '<div class="cal-day cal-day-empty"></div>';
        continue;
      }

      const events = deadlineMap[dateStr];
      const cls = [
        'cal-day',
        isToday ? 'cal-today'      : '',
        events  ? 'cal-has-events' : '',
      ].filter(Boolean).join(' ');

      let dots = '';
      if (events) {
        dots = '<div class="cal-dots">' +
          events.map(e =>
            `<span class="cal-dot" style="background:${PILLAR_COLORS[e.pillar] || '#6e7681'}" data-tip="${e.title}"></span>`
          ).join('') + '</div>';
      }

      html += `<div class="${cls}" data-date="${dateStr}">${date.getDate()}${dots}</div>`;
    }

    html += '</div></div>';
    return html;
  }

  document.addEventListener('DOMContentLoaded', function () {
    const calEl  = document.getElementById('deadline-calendar');
    const listEl = document.getElementById('deadline-upcoming');
    if (!calEl) return;

    const deadlines = JSON.parse(calEl.dataset.deadlines || '[]');

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    // Build date → deadlines map
    const deadlineMap = {};
    deadlines.forEach(function (d) {
      if (!deadlineMap[d.date]) deadlineMap[d.date] = [];
      deadlineMap[d.date].push(d);
    });

    // Render rolling 5-week grid
    calEl.innerHTML = buildWeekGrid(today, WEEKS_TO_SHOW, deadlineMap);

    // Upcoming list — next 3 deadlines from today
    const upcoming = deadlines
      .map(function (d) { return { ...d, _date: toLocal(d.date) }; })
      .filter(function (d) { return d._date >= today; })
      .sort(function (a, b) { return a._date - b._date; })
      .slice(0, 3);

    if (listEl) {
      if (upcoming.length === 0) {
        listEl.innerHTML = '<p class="sidebar-empty">No upcoming deadlines</p>';
      } else {
        const items = upcoming.map(function (d) {
          const diff  = Math.round((d._date - today) / 86400000);
          const color = PILLAR_COLORS[d.pillar] || '#6e7681';

          let urgencyLabel = '';
          let urgencyClass = '';
          if (diff === 0)       { urgencyLabel = ' — TODAY';    urgencyClass = 'is-urgent'; }
          else if (diff <= 14)  { urgencyLabel = ` — ${diff}d`; urgencyClass = 'is-urgent'; }
          else if (diff <= 30)  { urgencyLabel = ` — ${diff}d`; urgencyClass = 'is-soon';   }

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

    // Clicking a calendar day highlights its entry in the upcoming list
    calEl.querySelectorAll('.cal-day.cal-has-events').forEach(function (cell) {
      cell.addEventListener('click', function () {
        const dateStr = this.dataset.date;
        if (!listEl) return;
        listEl.querySelectorAll('.cal-upcoming-item').forEach(function (item) {
          item.classList.toggle('cal-highlighted', item.dataset.date === dateStr);
        });
        const match = listEl.querySelector(`.cal-upcoming-item[data-date="${dateStr}"]`);
        if (match) match.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      });
    });

    // Dot hover tooltip — appended to body to avoid grid overflow clipping
    const tip = document.createElement('div');
    tip.id = 'cal-dot-tip';
    tip.setAttribute('aria-hidden', 'true');
    document.body.appendChild(tip);

    calEl.querySelectorAll('.cal-dot[data-tip]').forEach(function (dot) {
      dot.addEventListener('mousemove', function (e) {
        tip.textContent = this.dataset.tip;
        tip.classList.add('is-visible');
        tip.style.left = (e.clientX + 12) + 'px';
        tip.style.top  = (e.clientY - 36) + 'px';
      });
      dot.addEventListener('mouseleave', function () {
        tip.classList.remove('is-visible');
      });
    });
  });
})();
