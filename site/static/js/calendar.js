/**
 * calendar.js — Deadline calendar widget.
 *
 * Two rendering modes controlled by data-mode attribute:
 *   weeks  (default) — rolling N-week grid, no month breaks. Used on homepage.
 *   months            — month-separated grids from today through last deadline. Used on /deadlines/.
 *
 * Configuration attributes on #deadline-calendar:
 *   data-deadlines  JSON array of deadline objects
 *   data-mode       "weeks" | "months"  (default: "weeks")
 *   data-weeks      number of weeks for "weeks" mode (default: 5)
 */

(function () {
  const WEEKS_DEFAULT = 5;

  const PILLAR_COLORS = {
    'Identity & Access':             '#a78bfa',
    'Endpoint & Device Management':  '#3fb950',
    'Collaboration & Productivity':  '#58a6ff',
    'AI & Copilot':                  '#f0883e',
    'Employee Experience':           '#f778ba',
    'Security & Compliance':         '#d2a8ff',
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

  function makeDots(events) {
    if (!events || !events.length) return '';
    return '<div class="cal-dots">' +
      events.map(function (e) {
        return `<span class="cal-dot" style="background:${PILLAR_COLORS[e.pillar] || '#6e7681'}" data-tip="${e.title}"></span>`;
      }).join('') +
    '</div>';
  }

  // ── Mode 1: Rolling week grid (homepage) ────────────────────────────────
  function buildWeekGrid(today, numWeeks, deadlineMap) {
    const gridStart = new Date(today);
    gridStart.setDate(today.getDate() - today.getDay());
    gridStart.setHours(0, 0, 0, 0);

    const gridEnd = new Date(gridStart);
    gridEnd.setDate(gridStart.getDate() + numWeeks * 7 - 1);

    const fmt     = { month: 'short', day: 'numeric' };
    const fmtYear = { month: 'short', day: 'numeric', year: 'numeric' };

    let html = '<div class="cal-month">';
    html += `<div class="cal-month-name">${gridStart.toLocaleString('default', fmt)} – ${gridEnd.toLocaleString('default', fmtYear)}</div>`;
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

      if (isPast) { html += '<div class="cal-day cal-day-empty"></div>'; continue; }

      const events = deadlineMap[dateStr];
      const cls = ['cal-day', isToday ? 'cal-today' : '', events ? 'cal-has-events' : ''].filter(Boolean).join(' ');
      html += `<div class="${cls}" data-date="${dateStr}">${date.getDate()}${makeDots(events)}</div>`;
    }
    html += '</div></div>';
    return html;
  }

  // ── Mode 2: Month-separated grids (deadlines page) ──────────────────────
  function buildMonthGrid(year, month, deadlineMap, today, trimPast) {
    const firstDay    = new Date(year, month, 1);
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const monthName   = firstDay.toLocaleString('default', { month: 'long', year: 'numeric' });

    const todayWeekStart = new Date(today);
    todayWeekStart.setDate(today.getDate() - today.getDay());
    todayWeekStart.setHours(0, 0, 0, 0);

    const startOffset = firstDay.getDay();
    const allDays = [];
    for (let i = 0; i < startOffset; i++) allDays.push(null);
    for (let d = 1; d <= daysInMonth; d++) allDays.push(d);
    while (allDays.length % 7 !== 0) allDays.push(null);

    let html = '<div class="cal-month">';
    html += `<div class="cal-month-name">${monthName}</div>`;
    html += '<div class="cal-grid">';
    for (const h of ['S', 'M', 'T', 'W', 'T', 'F', 'S']) {
      html += `<div class="cal-dow">${h}</div>`;
    }

    for (let w = 0; w < allDays.length; w += 7) {
      const week = allDays.slice(w, w + 7);

      if (trimPast) {
        const lastReal = [...week].reverse().find(function (d) { return d !== null; });
        if (lastReal === undefined) continue;
        const lastDate = new Date(year, month, lastReal);
        lastDate.setHours(0, 0, 0, 0);
        if (lastDate < todayWeekStart) continue;
      }

      for (const d of week) {
        if (d === null) { html += '<div class="cal-day cal-day-empty"></div>'; continue; }

        const date    = new Date(year, month, d);
        date.setHours(0, 0, 0, 0);
        const dateStr = toKey(date);
        const isToday = dateStr === toKey(today);
        const isPast  = date < today && !isToday;

        if (trimPast && isPast) { html += '<div class="cal-day cal-day-empty"></div>'; continue; }

        const events = deadlineMap[dateStr];
        const cls = ['cal-day', isToday ? 'cal-today' : '', isPast ? 'cal-past' : '', events ? 'cal-has-events' : ''].filter(Boolean).join(' ');
        html += `<div class="${cls}" data-date="${dateStr}">${d}${makeDots(events)}</div>`;
      }
    }
    html += '</div></div>';
    return html;
  }

  // ── Boot ────────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    const calEl  = document.getElementById('deadline-calendar');
    const listEl = document.getElementById('deadline-upcoming');
    if (!calEl) return;

    const deadlines   = JSON.parse(calEl.dataset.deadlines || '[]');
    const mode        = calEl.dataset.mode || 'weeks';
    const weeksToShow = parseInt(calEl.dataset.weeks, 10) || WEEKS_DEFAULT;

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const deadlineMap = {};
    deadlines.forEach(function (d) {
      if (!deadlineMap[d.date]) deadlineMap[d.date] = [];
      deadlineMap[d.date].push(d);
    });

    if (mode === 'months') {
      // Show current month (trimmed) + all subsequent months that have deadlines
      const thisYear  = today.getFullYear();
      const thisMonth = today.getMonth();

      // Find the latest future deadline date
      let maxDate = null;
      deadlines.forEach(function (d) {
        const dt = toLocal(d.date);
        if (dt >= today && (!maxDate || dt > maxDate)) maxDate = dt;
      });

      let calHtml = buildMonthGrid(thisYear, thisMonth, deadlineMap, today, true);

      if (maxDate) {
        let y = thisYear;
        let m = thisMonth + 1;
        if (m > 11) { y++; m = 0; }

        while (y < maxDate.getFullYear() || (y === maxDate.getFullYear() && m <= maxDate.getMonth())) {
          calHtml += buildMonthGrid(y, m, deadlineMap, today, false);
          m++;
          if (m > 11) { y++; m = 0; }
        }
      }

      calEl.innerHTML = calHtml;
    } else {
      // Rolling week grid
      calEl.innerHTML = buildWeekGrid(today, weeksToShow, deadlineMap);
    }

    // Upcoming list — next 3 (homepage only)
    if (listEl && mode === 'weeks') {
      const upcoming = deadlines
        .map(function (d) { return Object.assign({}, d, { _date: toLocal(d.date) }); })
        .filter(function (d) { return d._date >= today; })
        .sort(function (a, b) { return a._date - b._date; })
        .slice(0, 3);

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
  <div class="cal-upcoming-title">${d.url ? `<a href="${d.url}" target="_blank" rel="noopener">${d.title}</a>` : d.title}</div>
  <div class="cal-upcoming-pillar" style="color:${color}">${d.pillar}</div>
  <div class="cal-upcoming-action">${d.action}</div>
</div>`;
        }).join('');
        listEl.innerHTML = `<div class="cal-upcoming">${items}</div>`;
      }
    }

    // Click a calendar day → highlight in upcoming list
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

    // Dot tooltip
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
