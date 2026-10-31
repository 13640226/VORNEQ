/* Evidence Signal V2.3 — conceptual, local-only, no API or telemetry. */
(() => {
  "use strict";
  const root = document.querySelector("[data-evidence-signal-v23]");
  if (!root) return;
  const buttons = Array.from(root.querySelectorAll("[data-evidence-step]"));
  const descriptions = Array.from(root.querySelectorAll("[data-evidence-description]"));
  const announcement = root.querySelector("[data-evidence-announcement]");
  const valid = new Set(["source", "evidence", "context", "verification"]);
  let selectedKey = null;
  const select = (key, announce = false) => {
    if (!valid.has(key) || selectedKey === key) return;
    selectedKey = key;
    buttons.forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.evidenceStep === key));
    });
    descriptions.forEach((item) => {
      item.hidden = item.dataset.evidenceDescription !== key;
    });
    if (announce && announcement) {
      const activeDescription = descriptions.find((item) => item.dataset.evidenceDescription === key);
      announcement.textContent = activeDescription ? activeDescription.textContent.trim() : "";
    }
  };
  buttons.forEach((button) => button.addEventListener("click", () => select(button.dataset.evidenceStep, true)));
  select("source");
})();
