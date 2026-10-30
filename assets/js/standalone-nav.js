/* Close the standalone navigation language menu on Escape. */
(() => {
  document.querySelectorAll('.standalone-nav__language').forEach((details) => {
    if (details.dataset.escapeHandlerBound === 'true') return;
    const trigger = details.querySelector('summary');
    if (!trigger) return;
    details.dataset.escapeHandlerBound = 'true';
    details.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape' || !details.open) return;
      event.preventDefault();
      details.open = false;
      trigger.focus();
    });
  });
})();
