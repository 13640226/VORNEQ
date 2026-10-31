/* Evidence Signal V2.3 — conceptual, local-only, no API or telemetry. */
(() => {
  "use strict";
  const root = document.querySelector("[data-evidence-signal-v23]");
  if (!root) return;
  const buttons = Array.from(root.querySelectorAll("[data-evidence-step]"));
  const descriptions = Array.from(root.querySelectorAll("[data-evidence-description]"));
  const valid = new Set(["source", "evidence", "context", "verification"]);
  const select = (key) => {
    if (!valid.has(key)) return;
    buttons.forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.evidenceStep === key));
    });
    descriptions.forEach((item) => {
      item.hidden = item.dataset.evidenceDescription !== key;
    });
  };
  buttons.forEach((button) => button.addEventListener("click", () => select(button.dataset.evidenceStep)));
  select("source");
})();
