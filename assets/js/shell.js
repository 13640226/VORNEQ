/* VORNEQ App Shell V8 – UI-01: Drawer, Befehlspalette, aktive Navigation.
   Kein Inline-Skript, keine Inline-Styles (CSP script-src 'self').
   Das Theme verwaltet weiterhin theme-bootstrap.js / theme-preference.js. */
(function () {
  'use strict';

  var FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function qs(sel, root) { return (root || document).querySelector(sel); }
  function qsa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function normalize(text) {
    return (text || '').toLocaleLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').trim();
  }

  function markCurrent() {
    var path = window.location.pathname;
    qsa('.vq-nav__link, .vq-bottomnav__link[href]').forEach(function (link) {
      var url;
      try { url = new URL(link.getAttribute('href'), window.location.href); } catch (e) { return; }
      if (url.pathname === path && !url.hash) link.setAttribute('aria-current', 'page');
    });
  }

  function trapFocus(container, event) {
    var items = qsa(FOCUSABLE, container).filter(function (el) { return el.offsetParent !== null; });
    if (!items.length) return;
    var first = items[0];
    var last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }

  // Hintergrund während Drawer/Palette für Tastatur, Zeiger und Screenreader sperren.
  function setInert(elements, on) {
    elements.forEach(function (el) {
      if (!el) return;
      if (on) el.setAttribute('inert', ''); else el.removeAttribute('inert');
    });
  }

  function setupDrawer(shell) {
    var drawer = qs('[data-vq-drawer]', shell);
    var scrim = qs('[data-vq-scrim]', shell);
    var openBtn = qs('[data-vq-drawer-open]', shell);
    var closeBtn = qs('[data-vq-drawer-close]', shell);
    var mq = window.matchMedia('(max-width: 959px)');
    var lastFocus = null;
    var background = [qs('.vq-header', shell), qs('.vq-main', shell), qs('.vq-bottomnav', shell)];

    function isOpen() { return shell.hasAttribute('data-drawer-open'); }

    function open() {
      lastFocus = document.activeElement;
      shell.setAttribute('data-drawer-open', '');
      scrim.hidden = false;
      openBtn.setAttribute('aria-expanded', 'true');
      document.body.classList.add('vq-scroll-locked');
      setInert(background, true);
      var target = closeBtn || qs(FOCUSABLE, drawer);
      if (target) target.focus();
    }

    function close(restore) {
      if (!isOpen()) return;
      shell.removeAttribute('data-drawer-open');
      scrim.hidden = true;
      openBtn.setAttribute('aria-expanded', 'false');
      document.body.classList.remove('vq-scroll-locked');
      setInert(background, false);
      if (restore !== false && lastFocus && lastFocus.focus) lastFocus.focus();
    }

    openBtn.addEventListener('click', open);
    if (closeBtn) closeBtn.addEventListener('click', function () { close(); });
    scrim.addEventListener('click', function () { close(); });
    drawer.addEventListener('keydown', function (event) {
      if (!isOpen()) return;
      if (event.key === 'Escape') { event.preventDefault(); close(); }
      else if (event.key === 'Tab') trapFocus(drawer, event);
    });
    var onChange = function () { if (!mq.matches) close(false); };
    if (mq.addEventListener) mq.addEventListener('change', onChange); else if (mq.addListener) mq.addListener(onChange);

    return { close: close };
  }

  function setupPalette(drawerApi, shell) {
    var dialog = qs('[data-vq-cmd]');
    var input = qs('[data-vq-cmd-input]');
    var list = qs('[data-vq-cmd-list]');
    var empty = qs('[data-vq-cmd-empty]');
    if (!dialog || !input || !list) return;

    var entries = qsa('[data-vq-nav] .vq-nav__link').map(function (link, index) {
      var label = (qs('span', link) || link).textContent.trim();
      return { id: 'vq-cmd-opt-' + index, label: label, key: normalize(label), href: link.getAttribute('href') };
    });
    var visible = [];
    var active = -1;
    var lastFocus = null;

    function render() {
      var term = normalize(input.value);
      visible = entries.filter(function (e) { return !term || e.key.indexOf(term) !== -1; });
      list.textContent = '';
      visible.forEach(function (entry, i) {
        var li = document.createElement('li');
        li.id = entry.id;
        li.className = 'vq-cmd__option';
        li.setAttribute('role', 'option');
        li.setAttribute('aria-selected', 'false');
        li.textContent = entry.label;
        li.addEventListener('mousedown', function (event) { event.preventDefault(); });
        li.addEventListener('click', function () { go(entry); });
        li.addEventListener('mousemove', function () { if (active !== i) setActive(i); });
        list.appendChild(li);
      });
      empty.hidden = visible.length !== 0;
      input.setAttribute('aria-expanded', visible.length ? 'true' : 'false');
      setActive(visible.length ? 0 : -1);
    }

    function setActive(i) {
      var prev = active >= 0 && list.children[active];
      if (prev) prev.setAttribute('aria-selected', 'false');
      active = i;
      var cur = active >= 0 && list.children[active];
      if (cur) {
        cur.setAttribute('aria-selected', 'true');
        input.setAttribute('aria-activedescendant', cur.id);
        if (cur.scrollIntoView) cur.scrollIntoView({ block: 'nearest' });
      } else {
        input.setAttribute('aria-activedescendant', '');
      }
    }

    function go(entry) {
      if (entry && entry.href) window.location.assign(entry.href);
    }

    function open() {
      if (!dialog.hidden) return;
      if (drawerApi) drawerApi.close(false);
      lastFocus = document.activeElement;
      dialog.hidden = false;
      document.body.classList.add('vq-scroll-locked');
      setInert([shell], true);
      qsa('[data-vq-cmd-open]').forEach(function (b) { b.setAttribute('aria-expanded', 'true'); });
      input.value = '';
      render();
      input.focus();
    }

    function close() {
      if (dialog.hidden) return;
      dialog.hidden = true;
      document.body.classList.remove('vq-scroll-locked');
      setInert([shell], false);
      qsa('[data-vq-cmd-open]').forEach(function (b) { b.setAttribute('aria-expanded', 'false'); });
      if (lastFocus && lastFocus.focus) lastFocus.focus();
    }

    qsa('[data-vq-cmd-open]').forEach(function (b) {
      b.setAttribute('aria-expanded', 'false');
      b.addEventListener('click', open);
    });
    input.addEventListener('input', render);
    input.addEventListener('keydown', function (event) {
      var n = visible.length;
      if (event.key === 'ArrowDown') { event.preventDefault(); if (n) setActive((active + 1) % n); }
      else if (event.key === 'ArrowUp') { event.preventDefault(); if (n) setActive((active - 1 + n) % n); }
      else if (event.key === 'Home' && n) { event.preventDefault(); setActive(0); }
      else if (event.key === 'End' && n) { event.preventDefault(); setActive(n - 1); }
      else if (event.key === 'Enter') { event.preventDefault(); if (active >= 0) go(visible[active]); }
    });
    dialog.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') { event.preventDefault(); close(); }
      else if (event.key === 'Tab') { event.preventDefault(); input.focus(); }
    });
    dialog.addEventListener('mousedown', function (event) { if (event.target === dialog) close(); });
    document.addEventListener('keydown', function (event) {
      if ((event.ctrlKey || event.metaKey) && !event.altKey && (event.key === 'k' || event.key === 'K')) {
        event.preventDefault();
        if (dialog.hidden) open(); else close();
      }
    });
  }

  function setupLanguageMenu() {
    var menu = qs('[data-vq-lang]');
    if (!menu) return;
    document.addEventListener('click', function (event) {
      if (menu.open && !menu.contains(event.target)) menu.open = false;
    });
    menu.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && menu.open) {
        event.preventDefault();
        menu.open = false;
        var summary = qs('summary', menu);
        if (summary) summary.focus();
      }
    });
  }

  function init() {
    var shell = qs('[data-vq-shell]');
    if (!shell) return;
    markCurrent();
    var drawerApi = setupDrawer(shell);
    setupPalette(drawerApi, shell);
    setupLanguageMenu();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
}());
