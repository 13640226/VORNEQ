/* Evidence Signal UI Shell V1 — static, local DEMO only. No API or telemetry. */
(() => {
  "use strict";
  const root = document.querySelector("[data-evidence-signal-v23]");
  if (!root) return;

  const buttons = Array.from(root.querySelectorAll("[data-evidence-step]"));
  const panels = Array.from(root.querySelectorAll("[data-evidence-demo-panel]"));
  const announcement = root.querySelector("[data-evidence-announcement]");
  const valid = new Set(["source", "evidence", "context", "verification"]);

  const toggle = (key, forceClose = false) => {
    if (!valid.has(key)) return;
    const openPanel = panels.find((panel) => !panel.hidden);
    const shouldOpen = !forceClose && openPanel?.dataset.evidenceDemoPanel !== key;

    buttons.forEach((button) => {
      const active = shouldOpen && button.dataset.evidenceStep === key;
      button.setAttribute("aria-pressed", String(active));
      button.setAttribute("aria-expanded", String(active));
    });
    panels.forEach((panel) => {
      panel.hidden = !(shouldOpen && panel.dataset.evidenceDemoPanel === key);
    });

    if (announcement) {
      const heading = shouldOpen
        ? panels.find((panel) => panel.dataset.evidenceDemoPanel === key)?.querySelector(".world-evidence-panel__demo-title")
        : null;
      announcement.textContent = heading?.textContent.trim() || "";
    }
  };

  buttons.forEach((button) => {
    button.addEventListener("click", () => toggle(button.dataset.evidenceStep));
  });

  root.querySelectorAll("[data-evidence-close]").forEach((closeButton) => {
    closeButton.addEventListener("click", () => {
      const panel = closeButton.closest("[data-evidence-demo-panel]");
      if (!panel) return;
      const key = panel.dataset.evidenceDemoPanel;
      toggle(key, true);
      buttons.find((button) => button.dataset.evidenceStep === key)?.focus();
    });
  });

  root.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    const openPanel = panels.find((panel) => !panel.hidden);
    if (!openPanel) return;
    const key = openPanel.dataset.evidenceDemoPanel;
    toggle(key, true);
    buttons.find((button) => button.dataset.evidenceStep === key)?.focus();
    event.preventDefault();
  });
})();
