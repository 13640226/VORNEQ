(function () {
  'use strict';

  var brand = document.querySelector('[data-vorneq-brand]');
  if (!brand) return;

  var mark = brand.querySelector('.vorneq-mark');
  var homeUrl = brand.getAttribute('data-home-url') || brand.getAttribute('href');
  var isHome = brand.getAttribute('data-is-home') === 'true';
  var inFlight = false;
  var durationMs = 600;

  function prefersReducedMotion() {
    return Boolean(
      window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    );
  }

  function goToDestination() {
    if (isHome) {
      try {
        window.history.replaceState(
          null,
          '',
          window.location.pathname + window.location.search
        );
        window.location.reload();
      } catch (error) {
        window.location.replace(window.location.pathname + window.location.search);
      }
      return;
    }

    window.location.href = homeUrl;
  }

  function isModifiedActivation(event) {
    return event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey;
  }

  brand.addEventListener('click', function (event) {
    if (isModifiedActivation(event)) return;

    event.preventDefault();

    if (inFlight) return;

    if (prefersReducedMotion() || !mark) {
      goToDestination();
      return;
    }

    inFlight = true;
    brand.classList.add('is-logo-busy');
    brand.setAttribute('aria-busy', 'true');

    try {
      mark.classList.add('is-rotating');
      window.setTimeout(goToDestination, durationMs);
    } catch (error) {
      goToDestination();
    }
  });
}());
