/* VORNEQ Image Studio: one submission per page, no automatic paid retry.
 * Only talks to the same-origin VORNEQ image API. Never stores prompts,
 * job IDs or signed URLs in browser storage, logs or analytics.
 */
(() => {
  "use strict";

  const root = document.querySelector("[data-vq-image-studio]");
  if (!root) return;

  const form = root.querySelector("[data-vq-image-form]");
  const prompt = root.querySelector("[data-vq-image-prompt]");
  const size = root.querySelector("[data-vq-image-size]");
  const consent = root.querySelector("[data-vq-image-consent]");
  const submit = root.querySelector("[data-vq-image-submit]");
  const check = root.querySelector("[data-vq-image-check]");
  const status = root.querySelector("[data-vq-image-status]");
  const figure = root.querySelector("[data-vq-image-figure]");
  const preview = root.querySelector("[data-vq-image-preview]");
  const open = root.querySelector("[data-vq-image-open]");
  const csrf = form.querySelector("[name=csrfmiddlewaretoken]");
  const createUrl = root.dataset.createUrl;
  const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  let currentId = null;
  let sentOnce = false;
  let busy = false;

  function message(name) {
    status.textContent = status.dataset[name] || status.dataset.error;
  }

  function signedLink(value) {
    if (typeof value !== "string") return null;
    try {
      const candidate = new URL(value);
      if (candidate.protocol !== "https:" || candidate.username || candidate.password) return null;
      return candidate.href;
    } catch (_error) {
      return null;
    }
  }

  function showJob(job) {
    if (!job || job.id !== currentId) {
      message("invalid");
      return;
    }
    const states = ["queued", "running", "completed", "failed", "uncertain"];
    if (!states.includes(job.status)) {
      message("invalid");
      return;
    }
    message(job.status);
    if (job.status === "completed") {
      const url = signedLink(job.image_url);
      if (!url) {
        message("invalid");
        return;
      }
      preview.src = url;
      open.href = url;
      figure.hidden = false;
      open.hidden = false;
      check.hidden = true;
    } else {
      check.hidden = false;
      if (job.status === "failed" || job.status === "uncertain") {
        // Preserve the request identity and never submit another paid request.
        check.hidden = false;
      }
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (sentOnce || busy || !form.checkValidity()) {
      form.reportValidity();
      return;
    }
    if (!csrf || !createUrl || !window.crypto || typeof window.crypto.randomUUID !== "function") {
      message("error");
      return;
    }
    currentId = window.crypto.randomUUID();
    sentOnce = true; // Intentional: network failure may still have been billed.
    busy = true;
    submit.disabled = true;
    prompt.readOnly = true;
    size.disabled = true;
    consent.disabled = true;
    check.hidden = false;
    message("sending");
    try {
      const response = await fetch(createUrl, {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
          "X-CSRFToken": csrf.value
        },
        body: JSON.stringify({
          request_id: currentId, prompt: prompt.value, size: size.value
        })
      });
      if (response.status !== 202 && response.status !== 200) {
        message("error");
        return;
      }
      const job = await response.json();
      showJob(job);
      // No automatic POST retry, including on browser timeout.
    } catch (_error) {
      message("uncertain");
    } finally {
      busy = false;
    }
  });

  check.addEventListener("click", async () => {
    if (!sentOnce || busy || !uuidPattern.test(currentId)) return;
    busy = true;
    check.disabled = true;
    try {
      const response = await fetch(createUrl + encodeURIComponent(currentId) + "/", {
        method: "GET", credentials: "same-origin", cache: "no-store",
        headers: {"Accept": "application/json"}
      });
      if (response.status !== 200) {
        message("error");
        return;
      }
      showJob(await response.json());
    } catch (_error) {
      message("error");
    } finally {
      busy = false;
      check.disabled = false;
    }
  });
})();
