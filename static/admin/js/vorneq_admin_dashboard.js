/* VORNEQ admin home: model filter and Persian (Jalali) date.
 * Progressive enhancement only; the page works fully without it.
 * Served from 'self' to satisfy the site's script-src CSP.
 */
(function () {
  "use strict";

  function init() {
    var today = document.querySelector(".vorneq-dashboard .vq-today");
    if (today && document.documentElement.lang && document.documentElement.lang.indexOf("fa") === 0) {
      try {
        today.textContent = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
          weekday: "long", day: "numeric", month: "long", year: "numeric"
        }).format(new Date());
      } catch (e) { /* keep the server-rendered date */ }
    }

    var input = document.getElementById("vq-filter");
    var apps = document.querySelectorAll("[data-vq-app]");
    var noMatch = document.querySelector("[data-vq-no-match]");
    if (!input || !apps.length) return;

    input.addEventListener("input", function () {
      var q = input.value.trim().toLowerCase();
      var anyVisible = false;
      apps.forEach(function (app) {
        var appMatch = !q || app.getAttribute("data-vq-app").indexOf(q) !== -1;
        var visibleModels = 0;
        app.querySelectorAll("[data-vq-model]").forEach(function (row) {
          var show = appMatch || row.getAttribute("data-vq-model").indexOf(q) !== -1;
          row.hidden = !show;
          if (show) visibleModels += 1;
        });
        app.hidden = visibleModels === 0;
        if (!app.hidden) anyVisible = true;
      });
      if (noMatch) noMatch.hidden = anyVisible;
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
