/**
 * calendar.js — Deadline calendar for the homepage sidebar.
 *
 * Reads deadline data from #deadline-calendar[data-deadlines],
 * renders a mini month grid starting from today's week,
 * and an upcoming-deadlines list (next 5) below.
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

  function buildMonthGrid(year, month, deadlineMap, today, trimPast) {
    const firstDay   = new Date(year, month, 1);
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const monthName  = firstDay.toLocaleString('default', { month: 'long', year: 'numeric' });

    // Sunday of the week containing today
    const todayWeekStart = new Date(today);
    todayWeekStart.setDate(today.getDate() - today.getDay());
    todayWeekStart.setHours(0, 0, 0, 0);

    // Build flat array of day values (null = empty cell)
    const startOffset = firstDay.getDay();
    const allDays = [];
    for (let i = 0; i < startOffset; i++) allDays.push(null);
    for (let d = 1; d <= daysInMonth; d++) allDays.push(d);
    while (allDays.length % 7 !== 0) allDays.push(null);

    let html = `<div class="cal-month">`;
    html += `<div class="cal-month-name">${monthName}</div>`;
    html += `<div class="cal-grid">`;
    for (const h of ['S','M','T','W','T','F','S']) {
      html += `<div class="cal-dow">${h}</div>`;
    }

    for (let w = 0; w < allDays.length; w += 7) {
      const week = allDays.slice(w, w + 7);

      if (trimPast) {
        // Find last real day in this row
        const lastReal = [...week].reverse().find(d => d !== null);
        if (lastReal === undefined) continue; // trailing empty row

        const lastDate = new Date(year, month, lastReal);
        lastDate.setHours(0, 0, 0, 0);
        // Skip rows entirely before today's week
        if (lastDate < todayWeekStart) continue;
      }

      for (const d of week) {
        if (d === null) {
          html += `<div class="cal-day cal-day-empty"></div>`;
          continue;
        }

        const date    = new Date(year, month, d);
        date.setHours(0, 0, 0, 0);
        const dateStr = toKey(date);
        const isToday = dateStr === toKey(today);
        const isPast  = date < today && !isToday;

        // In trimPast mode, blank out past days within the current week row
        if (trimPast && isPast) {
          html += `<div class="cal-day cal-day-empty"></div>`;
          continue;
        }

        const events = deadlineMap[dateStr];
        const cls = [
          'cal-day',
          isToday ? 'cal-today'      : '',
          isPast  ? 'cal-past'       : '',
          events  ? 'cal-has-events' : '',
        ].filter(Boolean).join(' ');

        let dots = '';
        if (events) {
          dots = '<div class="cal-dots">' +
            events.map(e =>
              `<span class="cal-dot" style="background:${PILLAR_COLORS[e.pillar] || '#6e7681'}" data-tip="${e.title}"></span>`
            ).join('') + '</div>';
        }

        html += `<div class="${cls}" data-date="${dateStr}">${d}${dots}</div>`;
      }
    }

    html += `</div></div>`;
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

    // Current month only — trimmed to start from today's week, past days blanked
    const thisYear  = today.getFullYear();
    const thisMonth = today.getMonth();
    const calHtml = buildMonthGrid(thisYear, thisMonth, deadlineMap, today, true);

    calEl.innerHTML = calHtml;

    // Upcoming list — next 5 deadlines from today
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

    // Clicking a day scrolls/highlights its list item
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

    // Dot hover tooltip — follows mouse, avoids grid overflow clipping
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
