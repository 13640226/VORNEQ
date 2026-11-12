/* VORNEQ AI-first Homepage V1: UI only.
 * Questions are submitted to the existing Search route; no LLM call, chat
 * history persistence, private data access, or fabricated answers.
 */
(() => {
  "use strict";

  function start() {
    const root = document.querySelector("[data-vq-ai-workspace]");
    if (!root) return;
    const form = root.querySelector("[data-vq-composer]");
    const input = root.querySelector("[data-vq-composer-input]");
    const count = root.querySelector("[data-vq-composer-count]");
    if (!form || !input) return;
    const send = form.querySelector('button[type="submit"]');

    const limit = Math.min(Number(input.maxLength) || 200, 200);
    function updateCount() {
      if (count) count.textContent = input.value.length + "/" + limit;
      // Progressive enhancement: native 'required' still handles no-JS users.
      if (send) send.disabled = !input.value.trim();
    }
    updateCount();

    for (const button of root.querySelectorAll("[data-vq-example]")) {
      button.addEventListener("click", () => {
        const prompt = button.getAttribute("data-vq-prompt") || "";
        input.value = prompt.slice(0, limit);
        updateCount();
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
      });
    }

    input.addEventListener("input", updateCount);
    input.addEventListener("keydown", (event) => {
      // Enter can confirm an IME composition (e.g. Persian); never submit then.
      if (event.isComposing || event.keyCode === 229) return;
      if (event.key !== "Enter" || !(event.ctrlKey || event.metaKey)) return;
      event.preventDefault();
      if (form.requestSubmit) form.requestSubmit();
      else if (send) send.click(); // preserves native validity and submit handler
    });

    form.addEventListener("submit", (event) => {
      const question = input.value.trim();
      if (!question) {
        event.preventDefault();
        input.focus();
        updateCount();
        return;
      }
      input.value = question.slice(0, limit);
      updateCount();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
