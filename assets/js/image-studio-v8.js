/* Presentation only; no network calls or persistence. */
(() => {
  "use strict";
  const root = document.querySelector("[data-vq-image-studio]");
  if (!root) return;
  const prompt = root.querySelector("[data-vq-image-prompt]");
  const count = root.querySelector("[data-vq-image-count]");
  const size = root.querySelector("[data-vq-image-size]");
  const ratios = root.querySelector("[data-vq-ratios]");
  const buttons = [...ratios.querySelectorAll("[data-vq-ratio]")];
  const figure = root.querySelector("[data-vq-image-figure]");
  const empty = root.querySelector("[data-vq-image-empty]");
  const sync = () => {
    count.textContent = String(prompt.value.length);
    buttons.forEach(button => {
      button.disabled = size.disabled;
      button.setAttribute("aria-pressed", String(button.dataset.vqRatio === size.value));
    });
    empty.hidden = !figure.hidden;
  };
  buttons.forEach(button => button.addEventListener("click", () => {
    if (size.disabled) return;
    size.value = button.dataset.vqRatio;
    size.dispatchEvent(new Event("change", {bubbles: true}));
    sync();
  }));
  prompt.addEventListener("input", sync);
  size.addEventListener("change", sync);
  new MutationObserver(sync).observe(size, {attributes: true, attributeFilter: ["disabled"]});
  new MutationObserver(sync).observe(figure, {attributes: true, attributeFilter: ["hidden"]});
  ratios.hidden = false;
  sync();
})();
