(function () {
  'use strict';

  function initTopicChips() {
    var searchInput = document.querySelector('.discovery-search__input');
    var form = document.querySelector('.discovery-search');
    if (!searchInput || !form) return;

    document.querySelectorAll('[data-topic]').forEach(function (chip) {
      chip.addEventListener('click', function () {
        searchInput.value = chip.getAttribute('data-topic') || '';
        searchInput.focus();
        form.requestSubmit();
      });
    });
  }

  function initFeaturedKeyboardScroll() {
    var viewport = document.querySelector('[data-featured-viewport]');
    if (!viewport) return;

    viewport.addEventListener('keydown', function (event) {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
      var direction = event.key === 'ArrowRight' ? 1 : -1;
      if (document.documentElement.dir === 'rtl') direction *= -1;
      viewport.scrollBy({ left: direction * Math.max(260, viewport.clientWidth * 0.72), behavior: 'smooth' });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initTopicChips();
    initFeaturedKeyboardScroll();
  });
}());
