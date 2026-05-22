/**
 * top5-links.js — Adds "jump to section ↓" links to each Top 5 item.
 *
 * Finds the ordered list directly under the "Top 5" h2, extracts each
 * item's bold title, then locates the matching h3 in the post body and
 * inserts a small anchor link next to the bold title.
 */
(function () {
  document.addEventListener('DOMContentLoaded', function () {
    var content = document.querySelector('.post-content');
    if (!content) return;

    // Find the Top 5 h2 (Claude uses various phrasings)
    var headings = Array.from(content.querySelectorAll('h2'));
    var top5Heading = headings.find(function (h) {
      return /top\s*5/i.test(h.textContent);
    });
    if (!top5Heading) return;

    // The ordered list immediately follows the Top 5 h2
    var ol = top5Heading.nextElementSibling;
    while (ol && ol.tagName !== 'OL') {
      ol = ol.nextElementSibling;
    }
    if (!ol) return;

    // Collect all h3 elements in the post for matching
    var allH3 = Array.from(content.querySelectorAll('h3'));

    // Hugo heading slug: lowercase, spaces→hyphens, strip non-alphanum except hyphens
    function slugify(text) {
      return text.toLowerCase()
        .replace(/[^\w\s-]/g, '')
        .trim()
        .replace(/[\s_]+/g, '-');
    }

    // Score how well two strings match (shared words)
    function matchScore(a, b) {
      var wordsA = a.toLowerCase().split(/\W+/).filter(Boolean);
      var wordsB = b.toLowerCase().split(/\W+/).filter(Boolean);
      var setB = new Set(wordsB);
      return wordsA.filter(function (w) { return setB.has(w); }).length;
    }

    Array.from(ol.querySelectorAll('li')).forEach(function (li) {
      // Extract the bold title — Claude wraps it in <strong>
      var strong = li.querySelector('strong');
      if (!strong) return;
      var titleText = strong.textContent.trim();

      // Find best-matching h3 by word overlap
      var best = null;
      var bestScore = 0;
      allH3.forEach(function (h3) {
        var score = matchScore(titleText, h3.textContent);
        if (score > bestScore) {
          bestScore = score;
          best = h3;
        }
      });

      // Require at least 2 shared words to count as a match
      if (!best || bestScore < 2) return;

      // Use the h3's existing id if Hugo assigned one, otherwise derive it
      var targetId = best.id || slugify(best.textContent);
      if (!best.id) best.id = targetId;

      // Insert the jump link right after the <strong>
      var link = document.createElement('a');
      link.href = '#' + targetId;
      link.className = 'top5-jump';
      link.title = 'Jump to section';
      link.textContent = '↓';
      strong.insertAdjacentElement('afterend', link);
    });
  });
})();
