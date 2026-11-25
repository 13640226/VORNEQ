/* V6-02: restore the desktop sidebar state before first paint (avoids layout shift).
 * External file because the CSP forbids inline scripts. Reads one UI preference only. */
(function () {
  "use strict";
  try {
    if (localStorage.getItem("vq-side") === "collapsed") {
      document.documentElement.setAttribute("data-vq-side", "collapsed");
    }
  } catch (error) { /* storage unavailable: keep the expanded default */ }
})();
