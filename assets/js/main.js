"use strict";

(() => {

  const root =
    document.documentElement;

  const THEME_KEY =
    "saman-kherad-theme";


  /* ==========================================================
     HELPERS
     ========================================================== */

  function storageGet(key) {

    try {
      return localStorage.getItem(key);
    }
    catch {
      return null;
    }
  }


  function storageSet(
    key,
    value
  ) {

    try {
      localStorage.setItem(
        key,
        value
      );
    }
    catch {
      /* Storage is optional. */
    }
  }


  /* ==========================================================
     THEME
     ========================================================== */

  const validThemes =
    new Set([
      "light",
      "cream",
      "dark"
    ]);


  function applyTheme(
    theme,
    persist = true
  ) {

    if (
      !validThemes.has(theme)
    ) {
      return;
    }


    root.dataset.theme =
      theme;


    document
      .querySelectorAll(
        "[data-theme-choice]"
      )
      .forEach(button => {

        const active =
          button.dataset.themeChoice ===
          theme;

        button.setAttribute(
          "aria-pressed",
          active
            ? "true"
            : "false"
        );
      });


    if (persist) {

      storageSet(
        THEME_KEY,
        theme
      );
    }
  }


  const savedTheme =
    storageGet(
      THEME_KEY
    );


  if (
    savedTheme &&
    validThemes.has(savedTheme)
  ) {

    applyTheme(
      savedTheme,
      false
    );
  }
  else {

    applyTheme(
      root.dataset.theme || "dark",
      false
    );
  }


  document
    .querySelectorAll(
      "[data-theme-choice]"
    )
    .forEach(button => {

      button.addEventListener(
        "click",
        () => {

          applyTheme(
            button.dataset.themeChoice
          );
        }
      );
    });


  /* ==========================================================
     DRAWER
     ========================================================== */

  const trigger =
    document.getElementById(
      "drawerTrigger"
    );

  const closeButton =
    document.getElementById(
      "drawerClose"
    );

  const drawer =
    document.getElementById(
      "drawer"
    );

  const overlay =
    document.getElementById(
      "drawerOverlay"
    );

  const main =
    document.getElementById(
      "main"
    );


  let drawerOpen =
    false;


  function focusableItems() {

    if (!drawer) {
      return [];
    }

    return [
      ...drawer.querySelectorAll(
        [
          "a[href]",
          "button:not([disabled])",
          "input:not([disabled])",
          "textarea:not([disabled])",
          '[tabindex]:not([tabindex="-1"])'
        ].join(",")
      )
    ];
  }


  function setDrawer(
    open,
    returnFocus = false
  ) {

    if (
      !trigger ||
      !drawer ||
      !overlay
    ) {
      return;
    }


    drawerOpen =
      Boolean(open);


    trigger.setAttribute(
      "aria-expanded",
      String(drawerOpen)
    );


    if (drawerOpen) {

      drawer.hidden = false;
      overlay.hidden = false;


      if (
        "inert" in HTMLElement.prototype &&
        main
      ) {
        main.inert = true;
      }


      requestAnimationFrame(() => {

        drawer.classList.add(
          "is-open"
        );

        overlay.classList.add(
          "is-open"
        );
      });


      document.body.style.overflow =
        "hidden";


      setTimeout(() => {

        focusableItems()[0]
          ?.focus();

      }, 80);

    }
    else {

      drawer.classList.remove(
        "is-open"
      );

      overlay.classList.remove(
        "is-open"
      );


      if (
        "inert" in HTMLElement.prototype &&
        main
      ) {
        main.inert = false;
      }


      document.body.style.overflow =
        "";


      setTimeout(() => {

        drawer.hidden = true;
        overlay.hidden = true;

      }, 300);


      if (returnFocus) {

        setTimeout(() => {

          trigger.focus();

        }, 60);
      }
    }
  }


  trigger?.addEventListener(
    "click",
    () => {

      setDrawer(
        !drawerOpen,
        drawerOpen
      );
    }
  );


  closeButton?.addEventListener(
    "click",
    () => {

      setDrawer(
        false,
        true
      );
    }
  );


  overlay?.addEventListener(
    "click",
    () => {

      setDrawer(
        false,
        true
      );
    }
  );


  drawer
    ?.querySelectorAll(
      ".drawer__nav-link"
    )
    .forEach(link => {

      link.addEventListener(
        "click",
        () => {

          setDrawer(
            false,
            false
          );
        }
      );
    });


  document.addEventListener(
    "keydown",
    event => {

      if (
        event.key === "Escape" &&
        drawerOpen
      ) {

        setDrawer(
          false,
          true
        );

        return;
      }


      if (
        !drawerOpen ||
        event.key !== "Tab"
      ) {
        return;
      }


      const items =
        focusableItems();


      if (!items.length) {
        return;
      }


      const first =
        items[0];

      const last =
        items[
          items.length - 1
        ];


      if (
        event.shiftKey &&
        document.activeElement === first
      ) {

        event.preventDefault();
        last.focus();

      }
      else if (
        !event.shiftKey &&
        document.activeElement === last
      ) {

        event.preventDefault();
        first.focus();
      }
    }
  );


  const desktopMedia =
    window.matchMedia(
      "(min-width: 641px)"
    );


  const handleDesktop =
    event => {

      if (
        event.matches &&
        drawerOpen
      ) {

        setDrawer(
          false,
          false
        );
      }
    };


  if (
    typeof desktopMedia.addEventListener
      === "function"
  ) {

    desktopMedia.addEventListener(
      "change",
      handleDesktop
    );
  }
  else {

    desktopMedia.addListener(
      handleDesktop
    );
  }


  setDrawer(
    false,
    false
  );

})();
