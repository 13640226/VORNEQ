
document.addEventListener('DOMContentLoaded', function () {
  const open = document.getElementById('suchen-filter-open');
  const close = document.getElementById('suchen-filter-close');
  const panel = document.getElementById('suchen-filter-panel');
  const backdrop = document.getElementById('suchen-filter-backdrop');
  const mq = window.matchMedia('(max-width: 768px)');
  let expanded = false;
  function focusable() {
    return Array.from(panel.querySelectorAll('button, input, select, a[href], [tabindex]:not([tabindex="-1"])'))
      .filter(el => !el.disabled && el.getClientRects().length);
  }
  function toggle(next, restore) {
    expanded = next && mq.matches;
    panel.classList.toggle('is-mobile-open', expanded);
    backdrop.hidden = !expanded;
    open.setAttribute('aria-expanded', String(expanded));
    document.body.classList.toggle('suchen-filters-open', expanded);
    if (expanded) {
      const items = focusable();
      (items[0] || panel).focus();
    } else if (restore && mq.matches) {
      open.focus();
    }
  }
  open.addEventListener('click', () => toggle(true, false));
  close.addEventListener('click', () => toggle(false, true));
  backdrop.addEventListener('click', () => toggle(false, true));
  document.addEventListener('keydown', e => {
    if (!expanded) return;
    if (e.key === 'Escape') { e.preventDefault(); toggle(false, true); return; }
    if (e.key !== 'Tab') return;
    const items = focusable();
    if (!items.length) { e.preventDefault(); panel.focus(); return; }
    const first = items[0], last = items[items.length - 1];
    if (e.shiftKey && (document.activeElement === first || document.activeElement === panel || !panel.contains(document.activeElement))) {
      e.preventDefault(); last.focus();
    } else if (!e.shiftKey && (document.activeElement === last || document.activeElement === panel || !panel.contains(document.activeElement))) {
      e.preventDefault(); first.focus();
    }
  });
  mq.addEventListener('change', () => toggle(false, false));
});

document.addEventListener('DOMContentLoaded', function () {
  const grid = document.getElementById('suchen-results-grid');
  const buttons = document.querySelectorAll('[data-search-view]');
  buttons.forEach(button => button.addEventListener('click', () => {
    grid.classList.toggle('is-list', button.dataset.searchView === 'list');
    buttons.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
  }));
});
