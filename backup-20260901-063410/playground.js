"use strict";

(() => {

  const root =
    document.documentElement;


  /* ==========================================================
     HELPERS
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
      /* Storage unavailable: silently continue. */
    }
  }


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
     MOBILE MENU
     ========================================================== */

  const menuButton =
    document.getElementById(
      "mobileMenuButton"
    );

  const mobileMenu =
    document.getElementById(
      "mobileMenu"
    );

  const menuOverlay =
    document.getElementById(
      "mobileMenuOverlay"
    );


  let menuOpen = false;


  function setMenu(
    open,
    options = {}
  ) {

    const {
      returnFocus = false
    } = options;


    menuOpen =
      Boolean(open);


    if (
      !menuButton ||
      !mobileMenu ||
      !menuOverlay
    ) {
      return;
    }


    menuButton.setAttribute(
      "aria-expanded",
      String(menuOpen)
    );


    menuButton.setAttribute(
      "aria-label",
      menuOpen
        ? "بستن منوی اصلی"
        : "باز کردن منوی اصلی"
    );


    if (menuOpen) {

      mobileMenu.hidden = false;
      menuOverlay.hidden = false;


      requestAnimationFrame(() => {

        mobileMenu.classList.add(
          "is-open"
        );

        menuOverlay.classList.add(
          "is-open"
        );
      });


      document.body.style.overflow =
        "hidden";


      const firstLink =
        mobileMenu.querySelector("a");


      window.setTimeout(
        () => firstLink?.focus(),
        40
      );
    }
    else {

      mobileMenu.classList.remove(
        "is-open"
      );

      menuOverlay.classList.remove(
        "is-open"
      );


      document.body.style.overflow =
        "";


      window.setTimeout(() => {

        mobileMenu.hidden = true;
        menuOverlay.hidden = true;

      }, 280);


      if (returnFocus) {

        window.setTimeout(
          () => menuButton.focus(),
          40
        );
      }
    }
  }


  menuButton?.addEventListener(
    "click",
    () => {

      setMenu(
        !menuOpen,
        {
          returnFocus: menuOpen
        }
      );
    }
  );


  menuOverlay?.addEventListener(
    "click",
    () => {

      setMenu(
        false,
        {
          returnFocus: true
        }
      );
    }
  );


  document.addEventListener(
    "keydown",
    event => {

      if (
        event.key === "Escape" &&
        menuOpen
      ) {

        setMenu(
          false,
          {
            returnFocus: true
          }
        );
      }
    }
  );


  mobileMenu
    ?.querySelectorAll("a")
    .forEach(link => {

      link.addEventListener(
        "click",
        () => setMenu(false)
      );
    });


  const desktopMedia =
    window.matchMedia(
      "(min-width: 641px)"
    );


  function handleDesktopChange(event) {

    if (
      event.matches &&
      menuOpen
    ) {
      setMenu(false);
    }
  }


  if (
    typeof desktopMedia.addEventListener
      === "function"
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


  setMenu(false);

})();
