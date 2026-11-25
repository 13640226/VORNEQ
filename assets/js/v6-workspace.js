/* VORNEQ Product UI V6-02: application shell behaviour (UI only).
 * Sidebar collapse/drawer, theme toggle, header menus, keyboard shortcuts.
 * No network requests, no AI calls, no private data.
 */
(() => {
  "use strict";

  const root = document.documentElement;
  const desktop = window.matchMedia("(min-width: 1024px)");
  const LIGHT = ["light", "vorneq"];

  function store(key, value) {
    try { localStorage.setItem(key, value); } catch (error) { /* ignore */ }
  }

  /* ---------- Theme ---------- */
  function startTheme() {
    const button = document.querySelector("[data-vq-theme-toggle]");
    if (!button) return;
    const sync = () => button.setAttribute("aria-pressed", String(!LIGHT.includes(root.dataset.theme)));
    sync();
    button.addEventListener("click", () => {
      const next = LIGHT.includes(root.dataset.theme) ? "navy" : "light";
      root.dataset.theme = next;
      root.dataset.themePreference = next;
      root.style.colorScheme = next === "light" ? "light" : "dark";
      const meta = document.querySelector('meta[name="theme-color"]');
      if (meta) meta.setAttribute("content", next === "light" ? "#f5f7fa" : "#0b0f17");
      store("vorneq-theme", next);
      sync();
    });
  }

  /* ---------- Sidebar: collapse on desktop, drawer below 1024px ---------- */
  function startSidebar() {
    const side = document.querySelector("[data-vq-side]");
    const toggles = [...document.querySelectorAll("[data-vq-side-toggle]")];
    const backdrop = document.querySelector("[data-vq-side-backdrop]");
    if (!side || !toggles.length) return;
    let opener = null;

    const isOpen = () => root.getAttribute("data-vq-drawer") === "open";
    const collapsed = () => root.getAttribute("data-vq-side") === "collapsed";

    function syncExpanded() {
      const expanded = desktop.matches ? !collapsed() : isOpen();
      for (const toggle of toggles) {
        if (toggle.hasAttribute("data-vq-more")) toggle.setAttribute("aria-expanded", String(isOpen()));
        else toggle.setAttribute("aria-expanded", String(expanded));
      }
    }

    function openDrawer(from) {
      opener = from || null;
      root.setAttribute("data-vq-drawer", "open");
      if (backdrop) backdrop.hidden = false;
      syncExpanded();
      const first = side.querySelector("a[href]");
      if (first) first.focus();
    }

    function closeDrawer(returnFocus) {
      if (!isOpen()) return;
      root.removeAttribute("data-vq-drawer");
      if (backdrop) backdrop.hidden = true;
      syncExpanded();
      if (returnFocus && opener) opener.focus();
      opener = null;
    }

    for (const toggle of toggles) {
      toggle.addEventListener("click", () => {
        if (desktop.matches) {
          if (collapsed()) root.removeAttribute("data-vq-side");
          else root.setAttribute("data-vq-side", "collapsed");
          store("vq-side", collapsed() ? "collapsed" : "expanded");
          syncExpanded();
        } else if (isOpen()) {
          closeDrawer(true);
        } else {
          openDrawer(toggle);
        }
      });
    }
    if (backdrop) backdrop.addEventListener("click", () => closeDrawer(true));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && isOpen()) {
        event.preventDefault();
        closeDrawer(true);
      }
    });
    side.addEventListener("click", (event) => {
      if (!desktop.matches && event.target.closest("a[href]")) closeDrawer(false);
    });
    const onChange = () => { closeDrawer(false); syncExpanded(); };
    if (desktop.addEventListener) desktop.addEventListener("change", onChange);
    syncExpanded();
  }

  /* ---------- Header menus (<details>) ---------- */
  function startMenus() {
    const menus = [...document.querySelectorAll("[data-vq-menu]")];
    if (!menus.length) return;
    for (const menu of menus) {
      menu.addEventListener("toggle", () => {
        if (menu.open) for (const other of menus) if (other !== menu) other.open = false;
      });
    }
    document.addEventListener("click", (event) => {
      for (const menu of menus) if (menu.open && !menu.contains(event.target)) menu.open = false;
    });
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      for (const menu of menus) {
        if (menu.open) {
          menu.open = false;
          const summary = menu.querySelector("summary");
          if (summary) summary.focus();
        }
      }
    });
  }

  /* ---------- "/" and header search focus the composer ---------- */
  function startShortcuts() {
    const input = document.querySelector("[data-vq-composer-input]");
    if (!input) return;
    const focusComposer = () => {
      input.focus();
      input.scrollIntoView({ block: "center", behavior: "auto" });
    };
    const trigger = document.querySelector("[data-vq-search-shortcut]");
    if (trigger) {
      trigger.addEventListener("click", (event) => {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.button !== 0) return;
        event.preventDefault();
        focusComposer();
      });
    }
    document.addEventListener("keydown", (event) => {
      if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey || event.isComposing) return;
      const target = event.target;
      if (target.closest("input, textarea, select, [contenteditable='true']")) return;
      event.preventDefault();
      focusComposer();
    });
  }

  function start() {
    startTheme();
    startSidebar();
    startMenus();
    startShortcuts();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
