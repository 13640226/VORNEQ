(function () {
  'use strict';

  function initHomepageSignalNav() {
    var nav = document.querySelector('[data-homepage-signal-nav]');
    if (!nav) return;

    var links = Array.prototype.slice.call(nav.querySelectorAll('[data-signal-target]'));
    var sections = Array.prototype.slice.call(document.querySelectorAll('[data-homepage-signal-section]'));
    if (!links.length || !sections.length) return;

    var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var currentId = null;
    var pendingTargetId = null;
    var pulseTimer = null;

    function setActive(sectionId, shouldPulse) {
      if (!sectionId || currentId === sectionId) return;
      currentId = sectionId;

      links.forEach(function (link) {
        var isActive = link.dataset.signalTarget === sectionId;
        link.classList.toggle('is-active', isActive);
        link.classList.remove('is-pulsing');
        if (isActive) {
          link.setAttribute('aria-current', 'location');
          if (shouldPulse && !reduceMotion) {
            window.clearTimeout(pulseTimer);
            void link.offsetWidth;
            link.classList.add('is-pulsing');
            pulseTimer = window.setTimeout(function () {
              link.classList.remove('is-pulsing');
            }, 560);
          }
        } else {
          link.removeAttribute('aria-current');
        }
      });
    }

    function replaceHash(sectionId) {
      if (!window.history || !window.history.replaceState) return;
      var nextUrl = window.location.pathname + window.location.search + '#' + sectionId;
      window.history.replaceState(null, '', nextUrl);
    }

    function releasePendingTarget() {
      pendingTargetId = null;
    }

    function releasePendingTargetOnKeydown(event) {
      var scrollKeys = ['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End'];
      if (scrollKeys.indexOf(event.key) !== -1 || event.code === 'Space') {
        releasePendingTarget();
      }
    }

    window.addEventListener('wheel', releasePendingTarget, { passive: true });
    window.addEventListener('touchstart', releasePendingTarget, { passive: true });
    window.addEventListener('keydown', releasePendingTargetOnKeydown);

    links.forEach(function (link) {
      link.addEventListener('click', function (event) {
        var sectionId = link.dataset.signalTarget;
        var target = document.getElementById(sectionId);
        if (!target) return;

        event.preventDefault();
        setActive(sectionId, true);
        pendingTargetId = sectionId;

        if (window.history && window.history.pushState) {
          var nextUrl = window.location.pathname + window.location.search + '#' + sectionId;
          window.history.pushState(null, '', nextUrl);
        }

        target.scrollIntoView({
          behavior: reduceMotion ? 'auto' : 'smooth',
          block: 'start'
        });
      });
    });

    var observer = new IntersectionObserver(function (entries) {
      if (pendingTargetId) {
        var pendingTargetEntry = entries.find(function (entry) {
          return entry.isIntersecting && entry.target.id === pendingTargetId;
        });

        if (!pendingTargetEntry) return;

        var targetId = pendingTargetId;
        pendingTargetId = null;
        setActive(targetId, true);
        replaceHash(targetId);
        return;
      }

      var visible = entries
        .filter(function (entry) { return entry.isIntersecting; })
        .sort(function (a, b) { return b.intersectionRatio - a.intersectionRatio; });

      if (!visible.length) return;
      var sectionId = visible[0].target.id;
      if (!sectionId || sectionId === currentId) return;
      setActive(sectionId, true);
      replaceHash(sectionId);
    }, {
      root: null,
      rootMargin: '-18% 0px -48% 0px',
      threshold: [0.15, 0.35, 0.6]
    });

    sections.forEach(function (section) {
      observer.observe(section);
    });

    var hashId = window.location.hash.replace(/^#/, '');
    var hashTarget = hashId && document.getElementById(hashId);
    if (hashTarget && hashTarget.hasAttribute('data-homepage-signal-section')) {
      setActive(hashId, false);
    } else {
      setActive(sections[0].id, false);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHomepageSignalNav, { once: true });
  } else {
    initHomepageSignalNav();
  }
}());
