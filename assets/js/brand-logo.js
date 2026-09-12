(function () {
  'use strict';

  var brand = document.querySelector('[data-brand-logo]');
  if (!brand) return;

  var homeUrl = brand.getAttribute('data-brand-home-url') || brand.getAttribute('href') || '/';
  var onHome = brand.getAttribute('data-brand-on-home') === 'true';
  var reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var locked = false;
  var duration = 640;

  function completeActivation() {
    if (onHome) {
      if (window.location.hash && window.history && window.history.replaceState) {
        window.history.replaceState(null, '', window.location.pathname + window.location.search);
      }
      window.location.reload();
      return;
    }
    window.location.assign(homeUrl);
  }

  brand.addEventListener('click', function (event) {
    if (event.defaultPrevented) return;
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (locked) {
      event.preventDefault();
      return;
    }

    event.preventDefault();
    locked = true;

    if (reducedMotion) {
      completeActivation();
      return;
    }

    brand.classList.add('is-activating');
    window.setTimeout(completeActivation, duration);
  });
}());
