(() => {
  const controls = document.querySelector('[data-marketplace-layout]');
  const results = document.getElementById('marketplace-results');
  if (!controls || !results) return;
  controls.hidden = false;
  controls.addEventListener('click', event => {
    const button = event.target.closest('button[data-layout]');
    if (!button) return;
    results.classList.toggle('mkt-grid--list', button.dataset.layout === 'list');
    controls.querySelectorAll('button').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
  });
})();
