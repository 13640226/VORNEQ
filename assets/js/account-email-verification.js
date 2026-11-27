(() => {
  "use strict";
  const form = document.querySelector("[data-email-verification-form]");
  if (!form) return;
  const resend = form.querySelector("[data-email-resend]");
  const label = resend.querySelector("[data-email-resend-label]");
  const spinner = resend.querySelector(".account-email-spinner");
  const progress = form.querySelector("[data-email-progress]");
  const originalLabel = label.textContent;
  let pending = false;
  let action = null;
  form.addEventListener("submit", (event) => {
    if (pending) {
      event.preventDefault();
      return;
    }
    if (event.submitter !== resend) return;
    pending = true;
    // Disabled submit buttons are omitted from native form submission.
    action = document.createElement("input");
    action.type = "hidden";
    action.name = resend.name;
    action.value = resend.value;
    form.appendChild(action);
    resend.disabled = true;
    form.setAttribute("aria-busy", "true");
    spinner.hidden = false;
    label.textContent = progress.dataset.sendingLabel;
    progress.textContent = progress.dataset.sendingLabel;
  });
  window.addEventListener("pageshow", () => {
    if (!pending) return;
    pending = false;
    if (action) action.remove();
    action = null;
    resend.disabled = false;
    form.removeAttribute("aria-busy");
    spinner.hidden = true;
    label.textContent = originalLabel;
    progress.textContent = "";
  });
})();
