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

  // Entry type — separate axis from pillar. Kept in sync manually with
  // $typeLabels/$typeColors in deadlines.html. "feature" is the default
  // for any older deadlines.json entry written before the type field
  // existed, matching that template's `.type | default "feature"`.
  const TYPE_LABELS = { deadline: 'Deadline', feature: 'New Feature', report: 'Reporting', watch: 'Watching' };

  const PILLAR_COLORS = {
    'Identity & Access':             '#a78bfa',
    'Endpoint & Device Management':  '#3fb950',
    'Collaboration & Productivity':  '#58a6ff',
    'AI & Copilot':                  '#f0883e',
    'Employee Experience':           '#f778ba',
    'Security & Compliance':         '#d2a8ff',
  };

  // Per-pillar fill-style, second visual cue beyond color — same mapping as
  // PILLAR_STYLE in the Tag Universe globe prototype and the
  // .cal-style-* / .pillar-style-* rules in main.css. Kept in sync manually
  // with post-card-signals.html / deadlines-sidebar.html / deadlines.html /
  // collapsible.js, same as PILLAR_COLORS above.
  const PILLAR_STYLES = {
    'Identity & Access':             '',
    'Endpoint & Device Management':  'cal-style-donut',
    'Collaboration & Productivity':  'cal-style-stripe',
    'AI & Copilot':                  'cal-style-dashed',
    'Employee Experience':           'cal-style-gradient',
    'Security & Compliance':         'cal-style-halo',
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

  // Shared urgency thresholds — used by the homepage "upcoming" sidebar list
  // and the /deadlines/ page's countdown badges + stat strip, so all three
  // agree on what counts as urgent/soon.
  function urgencyInfo(diff) {
    if (diff < 0)        return { label: 'Past',        cls: 'is-overdue' };
    if (diff === 0)      return { label: 'Today',       cls: 'is-urgent'  };
    if (diff <= 14)      return { label: `${diff}d`,    cls: 'is-urgent'  };
    if (diff <= 30)      return { label: `${diff}d`,    cls: 'is-soon'    };
    return                      { label: `${diff}d`,    cls: ''           };
  }

  function makeDots(events) {
    if (!events || !events.length) return '';
    return '<div class="cal-dots">' +
      events.map(function (e) {
        const style = PILLAR_STYLES[e.pillar] || '';
        const typeLabel = TYPE_LABELS[e.type] || TYPE_LABELS.feature;
        const tip = `${typeLabel}: ${e.title}`;
        return `<span class="cal-dot ${style}" style="background:${PILLAR_COLORS[e.pillar] || '#6e7681'}" data-tip="${tip}"></span>`;
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
        listEl.innerHTML = '<p class="sidebar-empty">Nothing on the calendar right now</p>';
      } else {
        const items = upcoming.map(function (d) {
          const diff  = Math.round((d._date - today) / 86400000);
          const color = PILLAR_COLORS[d.pillar] || '#6e7681';
          const info  = urgencyInfo(diff);
          const urgencyLabel = (diff <= 30) ? ` — ${diff === 0 ? 'TODAY' : info.label}` : '';
          const urgencyClass = (diff <= 30) ? info.cls : '';
          const typeLabel = TYPE_LABELS[d.type] || TYPE_LABELS.feature;
          return `
<div class="cal-upcoming-item ${urgencyClass}" data-date="${d.date}" style="border-left-color:${color}">
  <div class="cal-upcoming-date">${d.date}${urgencyLabel}</div>
  <div class="cal-upcoming-title">${d.url ? `<a href="${d.url}" target="_blank" rel="noopener">${d.title}</a>` : d.title}</div>
  <div class="cal-upcoming-pillar" style="color:${color}">${d.pillar} &middot; ${typeLabel}</div>
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

    // ── Countdown badges on /deadlines/ pillar cards ──────────────────────
    // No-op on the homepage (no .deadline-card[data-date] elements there).
    // Watching-tier cards deliberately carry no data-date, so they're
    // skipped automatically.
    document.querySelectorAll('.deadline-card[data-date]').forEach(function (card) {
      const dt   = toLocal(card.dataset.date);
      const diff = Math.round((dt - today) / 86400000);
      const info = urgencyInfo(diff);
      const badge = card.querySelector('.deadline-card-countdown');
      if (badge) {
        badge.textContent = info.label;
        if (info.cls) badge.classList.add(info.cls);
      }
    });

    // ── Stat strip on /deadlines/ (element only exists on that page) ──────
    const statsEl = document.getElementById('deadline-stats');
    if (statsEl) {
      const upcoming = deadlines
        .map(function (d) { return Object.assign({}, d, { _date: toLocal(d.date) }); })
        .filter(function (d) { return d._date >= today; });

      const urgentCount = upcoming.filter(function (d) {
        return Math.round((d._date - today) / 86400000) <= 14;
      }).length;
      const soonCount = upcoming.filter(function (d) {
        const diff = Math.round((d._date - today) / 86400000);
        return diff > 14 && diff <= 30;
      }).length;
      const pillarCount = new Set(upcoming.map(function (d) { return d.pillar; })).size;

      [
        { num: upcoming.length, label: 'Upcoming key dates',       cls: '' },
        { num: urgentCount,     label: 'Within 14 days',           cls: urgentCount > 0 ? 'exec-stat-card-high' : '' },
        { num: soonCount,       label: '15–30 days out',      cls: soonCount   > 0 ? 'exec-stat-card-med'  : '' },
        { num: pillarCount,     label: 'Practice areas affected',  cls: '' },
      ].forEach(function (s) {
        const card = document.createElement('div');
        card.className = 'exec-stat-card ' + s.cls;
        card.innerHTML = '<div class="exec-stat-number">' + s.num + '</div>' +
          '<div class="exec-stat-label">' + s.label + '</div>';
        statsEl.appendChild(card);
      });
    }

    // ── Type filters (/deadlines/ page only — element only exists there) ──
    const filterEls = document.querySelectorAll('.key-dates-filter');
    if (filterEls.length) {
      const cards = document.querySelectorAll('.deadline-card[data-type]');
      const groups = document.querySelectorAll('.deadlines-pillar-group, .deadlines-watching-section');

      function applyFilter(type) {
        cards.forEach(function (card) {
          card.style.display = (type === 'all' || card.dataset.type === type) ? '' : 'none';
        });
        // Hide a pillar/watching section entirely once every card inside it
        // is filtered out, rather than leaving an empty-looking heading.
        groups.forEach(function (group) {
          const visible = group.querySelectorAll('.deadline-card[data-type]:not([style*="display: none"])');
          group.style.display = visible.length ? '' : 'none';
        });
      }

      filterEls.forEach(function (btn) {
        btn.addEventListener('click', function () {
          filterEls.forEach(function (b) { b.classList.remove('is-active'); });
          btn.classList.add('is-active');
          applyFilter(btn.dataset.filterType);
        });
      });
    }
  });
})();
