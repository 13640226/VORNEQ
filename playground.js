"use strict";

(() => {

  const root =
    document.documentElement;


  /* ==========================================================
     STORAGE
     ========================================================== */

  function safeStorageGet(key) {

    try {
      return localStorage.getItem(key);
    }
    catch {
      return null;
    }
  }


  function safeStorageSet(
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
      /* Continue without persistence. */
    }
  }


  /* ==========================================================
     BUTTON STATE
     ========================================================== */

  function setPressed(
    buttons,
    activeKey
  ) {

    Object.entries(buttons)
      .forEach(([key, button]) => {

        if (!button) {
          return;
        }

        button.setAttribute(
          "aria-pressed",
          key === activeKey
            ? "true"
            : "false"
        );
      });
  }


  /* ==========================================================
     THEME
     ========================================================== */

  const themeButtons = {

    light:
      document.getElementById(
        "themeLight"
      ),

    cream:
      document.getElementById(
        "themeCream"
      ),

    dark:
      document.getElementById(
        "themeDark"
      )
  };


  const THEME_KEY =
    "saman-kherad-theme";


  function setTheme(
    theme,
    persist = true
  ) {

    if (
      !Object.prototype
        .hasOwnProperty
        .call(
          themeButtons,
          theme
        )
    ) {
      return;
    }


    root.dataset.theme =
      theme;


    setPressed(
      themeButtons,
      theme
    );


    if (persist) {

      safeStorageSet(
        THEME_KEY,
        theme
      );
    }
  }


  Object.entries(themeButtons)
    .forEach(([theme, button]) => {

      button?.addEventListener(
        "click",
        () => setTheme(theme)
      );
    });


  /* ==========================================================
     DIRECTION
     ========================================================== */

  const directionButtons = {

    rtl:
      document.getElementById(
        "dirRtl"
      ),

    ltr:
      document.getElementById(
        "dirLtr"
      )
  };


  function setDirection(direction) {

    if (
      !Object.prototype
        .hasOwnProperty
        .call(
          directionButtons,
          direction
        )
    ) {
      return;
    }


    root.dir =
      direction;


    root.lang =
      direction === "rtl"
        ? "fa"
        : "en";


    setPressed(
      directionButtons,
      direction
    );
  }


  Object.entries(directionButtons)
    .forEach(([direction, button]) => {

      button?.addEventListener(
        "click",
        () => setDirection(direction)
      );
    });


  /* ==========================================================
     DRAWER
     ========================================================== */

  const drawerTrigger =
    document.getElementById(
      "drawerTrigger"
    );

  const drawerClose =
    document.getElementById(
      "drawerClose"
    );

  const drawer =
    document.getElementById(
      "drawer"
    );

  const drawerOverlay =
    document.getElementById(
      "drawerOverlay"
    );


  let drawerOpen = false;


  function getDrawerFocusable() {

    if (!drawer) {
      return [];
    }

    return [
      ...drawer.querySelectorAll(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
    ];
  }


  function setDrawer(
    open,
    options = {}
  ) {

    const {
      returnFocus = false
    } = options;


    drawerOpen =
      Boolean(open);


    if (
      !drawerTrigger ||
      !drawer ||
      !drawerOverlay
    ) {
      return;
    }


    drawerTrigger.setAttribute(
      "aria-expanded",
      String(drawerOpen)
    );


    drawerTrigger.setAttribute(
      "aria-label",
      drawerOpen
        ? "بستن منوی اصلی"
        : "باز کردن منوی اصلی"
    );


    if (drawerOpen) {

      drawer.hidden =
        false;

      drawerOverlay.hidden =
        false;


      requestAnimationFrame(() => {

        drawer.classList.add(
          "is-open"
        );

        drawerOverlay.classList.add(
          "is-open"
        );
      });


      document.body.style.overflow =
        "hidden";


      const focusable =
        getDrawerFocusable();


      window.setTimeout(
        () => focusable[0]?.focus(),
        60
      );

      return;
    }


    drawer.classList.remove(
      "is-open"
    );

    drawerOverlay.classList.remove(
      "is-open"
    );


    document.body.style.overflow =
      "";


    window.setTimeout(() => {

      drawer.hidden =
        true;

      drawerOverlay.hidden =
        true;

    }, 280);


    if (returnFocus) {

      window.setTimeout(
        () => drawerTrigger.focus(),
        60
      );
    }
  }


  drawerTrigger?.addEventListener(
    "click",
    () => {

      setDrawer(
        !drawerOpen,
        {
          returnFocus: drawerOpen
        }
      );
    }
  );


  drawerClose?.addEventListener(
    "click",
    () => {

      setDrawer(
        false,
        {
          returnFocus: true
        }
      );
    }
  );


  drawerOverlay?.addEventListener(
    "click",
    () => {

      setDrawer(
        false,
        {
          returnFocus: true
        }
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

          setDrawer(false);
        }
      );
    });


  /* ==========================================================
     KEYBOARD
     ========================================================== */

  document.addEventListener(
    "keydown",
    event => {

      if (
        event.key === "Escape" &&
        drawerOpen
      ) {

        event.preventDefault();

        setDrawer(
          false,
          {
            returnFocus: true
          }
        );

        return;
      }


      if (
        !drawerOpen ||
        event.key !== "Tab"
      ) {
        return;
      }


      const focusable =
        getDrawerFocusable();


      if (!focusable.length) {
        return;
      }


      const first =
        focusable[0];

      const last =
        focusable[
          focusable.length - 1
        ];


      if (
        event.shiftKey &&
        document.activeElement === first
      ) {

        event.preventDefault();

        last.focus();

        return;
      }


      if (
        !event.shiftKey &&
        document.activeElement === last
      ) {

        event.preventDefault();

        first.focus();
      }
    }
  );


  /* ==========================================================
     RESIZE
     ========================================================== */

  const desktopMedia =
    window.matchMedia(
      "(min-width: 641px)"
    );


  function handleDesktopChange(event) {

    if (
      event.matches &&
      drawerOpen
    ) {

      setDrawer(false);
    }
  }


  if (
    typeof desktopMedia
      .addEventListener === "function"
  ) {

    desktopMedia.addEventListener(
      "change",
      handleDesktopChange
    );
  }
  else {

    desktopMedia.addListener(
      handleDesktopChange
    );
  }


  /* ==========================================================
     INITIAL STATE
     ========================================================== */

  const savedTheme =
    safeStorageGet(
      THEME_KEY
    );


  const prefersDark =
    window.matchMedia(
      "(prefers-color-scheme: dark)"
    ).matches;


  const initialTheme =
    savedTheme &&
    Object.prototype
      .hasOwnProperty
      .call(
        themeButtons,
        savedTheme
      )
      ? savedTheme
      : prefersDark
        ? "dark"
        : "light";


  setTheme(
    initialTheme,
    false
  );


  setDirection(
    root.dir === "ltr"
      ? "ltr"
      : "rtl"
  );


  setDrawer(false);

})();
