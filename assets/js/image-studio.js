/* VORNEQ Image Studio: explicit submissions only; recovery and polling are GET-only.
 * Keep only a user-scoped job UUID and acknowledgment in browser storage.
 * Never persist prompts, signed URLs, credentials or provider data.
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
  const ack = root.querySelector("[data-vq-image-ack]");
  const ackLabel = root.querySelector("[data-vq-image-ack-label]");
  const newRequest = root.querySelector("[data-vq-image-new]");
  const csrf = form.querySelector("[name=csrfmiddlewaretoken]");
  const createUrl = root.dataset.createUrl;
  const userId = root.dataset.userId;
  const storageKey = userId ? "vq.image.recovery." + userId : null;
  const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  const states = ["queued", "running", "completed", "failed", "uncertain"];
  const delays = [2000, 3000, 5000, 8000];
  const maxPolls = 20;
  const refusals = new Map([
    ["invalid_request", [400, "rejected"]],
    ["invalid_request_id", [400, "rejected"]],
    ["invalid_prompt", [400, "rejected"]],
    ["unsupported_size", [400, "rejected"]],
    ["request_id_conflict", [400, "rejected"]],
    ["rate_limited", [429, "rateLimited"]],
    ["active_queue_full", [429, "queueFull"]],
    ["global_active_queue_full", [429, "queueFull"]],
    ["global_daily_cap", [429, "dailyLimit"]],
    ["user_daily_cap", [429, "dailyLimit"]],
    ["service_misconfigured", [503, "misconfigured"]]
  ]);
  let currentId = null;
  let sentOnce = false;
  let busy = false;
  let polling = false;
  let pending = null;
  let polls = 0;
  let timer = null;
  let generation = 0;
  let acknowledged = false;
  let allowNew = false;
  let recovering = true;

  function message(name, seconds) {
    const brand = root.querySelector("[data-vq-ai-brand]");
    if (brand) brand.dataset.state = ["sending", "queued", "running"].includes(name) ? "thinking" : ["wait", "completed"].includes(name) ? "idle" : "error";
    status.dataset.state = name;
    const text = status.dataset[name] || status.dataset.error;
    status.textContent = seconds === undefined ? text : text.replace("{seconds}", String(seconds));
  }

  function loadIdentity() {
    if (!storageKey) return null;
    try {
      const data = JSON.parse(window.localStorage.getItem(storageKey) || "null");
      if (data && typeof data.id === "string" && uuidPattern.test(data.id)) {
        return {id: data.id, acknowledged: data.acknowledged === true};
      }
    } catch (_error) { /* Browser storage is optional. */ }
    return null;
  }

  function rememberIdentity() {
    if (!storageKey || !currentId) return false;
    try {
      window.localStorage.setItem(storageKey, JSON.stringify({id: currentId, acknowledged}));
      return true;
    } catch (_error) { return false; }
  }

  function forgetIdentity() {
    if (!storageKey) return;
    try { window.localStorage.removeItem(storageKey); } catch (_error) {}
  }

  function lockForm(locked) {
    submit.disabled = locked;
    prompt.readOnly = locked;
    size.disabled = locked;
    consent.disabled = locked;
  }

  function signedLink(value) {
    if (typeof value !== "string") return null;
    try {
      const candidate = new URL(value);
      if (candidate.protocol !== "https:" || candidate.username || candidate.password) return null;
      return candidate.href;
    } catch (_error) { return null; }
  }

  // Tells the independent gallery module which job finished. Never carries job state back.
  function announce(id) {
    if (typeof root.dispatchEvent !== "function" || typeof CustomEvent !== "function") return;
    root.dispatchEvent(new CustomEvent("vq-image:completed", {detail: {id}}));
  }

  function stopTimer() {
    if (timer !== null) clearTimeout(timer);
    timer = null;
  }

  function stopPolling() {
    polling = false;
    stopTimer();
  }

  function showAck() {
    ackLabel.hidden = false;
    ack.checked = acknowledged;
    ack.disabled = acknowledged;
  }

  function hideAck() {
    ackLabel.hidden = true;
  }

  function newAvailable(value) {
    allowNew = value;
    newRequest.hidden = !value;
  }

  function schedule() {
    stopTimer();
    if (!polling || busy || document.hidden || navigator.onLine === false) return;
    if (polls >= maxPolls) {
      polling = false;
      status.textContent += " " + status.dataset.pollStopped;
      const brand = root.querySelector("[data-vq-ai-brand]");
      if (brand) brand.dataset.state = "error";
      return;
    }
    const token = generation;
    timer = setTimeout(() => {
      timer = null;
      if (token !== generation || !polling || busy || document.hidden || navigator.onLine === false) return;
      polls += 1;
      fetchStatus();
    }, delays[Math.min(polls, delays.length - 1)]);
  }

  function adopt(id, acked = false) {
    stopPolling();
    generation += 1;
    currentId = id;
    acknowledged = acked;
    sentOnce = true;
    polls = 0;
    newAvailable(false);
    lockForm(true);
    check.hidden = false;
    rememberIdentity();
  }

  function unknown(name = "uncertain") {
    newAvailable(false);
    check.hidden = false;
    showAck();
    message(name);
    polling = true;
  }

  function showJob(job) {
    if (!job || job.id !== currentId || !states.includes(job.status)) {
      unknown("invalid");
      return;
    }
    message(job.status);
    if (job.status === "queued" || job.status === "running") {
      hideAck();
      polling = true;
      return;
    }
    stopPolling();
    if (job.status === "uncertain") {
      showAck();
      newAvailable(false);
      return;
    }
    hideAck();
    if (job.status === "completed") {
      const url = signedLink(job.image_url);
      if (!url) {
        // A completed job with an unusable link remains recoverable by GET.
        message("invalid");
        return;
      }
      preview.src = url;
      open.href = url;
      figure.hidden = false;
      open.hidden = false;
      announce(job.id);
      // Keep manual status available to renew the signed URL.
      check.hidden = false;
    }
    newAvailable(true);
  }

  // Single in-flight GET with a finite deadline. GET timeout never retries POST.
  async function read(url) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(url, {
        method: "GET", credentials: "same-origin", cache: "no-store",
        headers: {"Accept": "application/json"}, signal: controller.signal
      });
      return {status: response.status, body: response.status === 200 ? await response.json() : null};
    } finally {
      clearTimeout(timeout);
    }
  }

  async function fetchStatus() {
    if (busy || !currentId || !uuidPattern.test(currentId)) return;
    stopTimer();
    const token = generation;
    busy = true;
    check.disabled = true;
    try {
      const result = await read(createUrl + encodeURIComponent(currentId) + "/");
      if (token !== generation) return;
      if (result.status === 200) {
        showJob(result.body);
      } else if (result.status === 401 || result.status === 404) {
        // A missing or inaccessible request is not proof that it was never paid.
        unknown("unknownMissing");
      } else {
        unknown("error");
      }
    } catch (_error) {
      if (token === generation) unknown("error");
    } finally {
      busy = false;
      check.disabled = false;
      if (token === generation) schedule();
    }
  }

  async function recover(includeLatest = true) {
    if (busy) return;
    busy = true;
    recovering = true;
    lockForm(true);
    check.hidden = true;
    try {
      const saved = includeLatest ? loadIdentity() : null;
      if (saved) {
        adopt(saved.id, saved.acknowledged);
        // Preserve unknown POST identity even if the server currently returns 404.
        pending = saved.id;
      } else {
        const active = await read(createUrl + "?active=1");
        if (active.status !== 200 || !active.body || !Array.isArray(active.body.results)) {
          throw new Error("recovery");
        }
        const job = active.body.results[0];
        if (job) {
          if (typeof job.id !== "string" || !uuidPattern.test(job.id) || !["queued", "running"].includes(job.status)) throw new Error("recovery");
          adopt(job.id);
          pending = job.id;
        } else if (includeLatest) {
          const latest = await read(createUrl + "?latest=1");
          if (latest.status !== 200 || !latest.body || !("id" in latest.body)) throw new Error("recovery");
          if (latest.body.id !== null) {
            if (typeof latest.body.id !== "string" || !uuidPattern.test(latest.body.id)) throw new Error("recovery");
            adopt(latest.body.id);
            pending = latest.body.id;
          }
        }
      }
      recovering = false;
      if (!currentId) {
        lockForm(false);
        message("wait");
      }
    } catch (_error) {
      message("recoveryError");
      check.hidden = false;
    } finally {
      busy = false;
      if (pending) {
        pending = null;
        await fetchStatus();
      }
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (sentOnce || recovering || busy || !form.checkValidity()) {
      form.reportValidity();
      return;
    }
    if (!csrf || !createUrl || !window.crypto || typeof window.crypto.randomUUID !== "function") {
      message("error");
      return;
    }
    currentId = window.crypto.randomUUID();
    generation += 1;
    sentOnce = true;
    acknowledged = false;
    polls = 0;
    if (!rememberIdentity()) {
      // A new request must be recoverable before any paid submission.
      currentId = null;
      sentOnce = false;
      message("recoveryError");
      return;
    }
    busy = true;
    lockForm(true);
    newAvailable(false);
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
        body: JSON.stringify({request_id: currentId, prompt: prompt.value, size: size.value})
      });
      const body = await response.json();
      if (response.status === 202 || response.status === 200) {
        showJob(body);
      } else {
        const refusal = body && body.request_rejected === true && refusals.get(body.error_code);
        if (refusal && refusal[0] === response.status && body.error === body.error_code) {
          const seconds = body.retry_after_seconds;
          if (response.status === 429 &&
              (!Number.isInteger(seconds) || seconds < 1 || String(seconds) !== response.headers.get("Retry-After"))) {
            unknown("error");
          } else {
            stopPolling();
            hideAck();
            forgetIdentity();
            currentId = null;
            check.hidden = true;
            message(refusal[1], refusal[1] === "rateLimited" ? seconds : undefined);
            newAvailable(true);
          }
        } else {
          unknown("error");
        }
      }
    } catch (_error) {
      unknown();
    } finally {
      busy = false;
      schedule();
    }
  });

  check.addEventListener("click", () => {
    if (currentId) fetchStatus();
    else recover();
  });
  ack.addEventListener("change", () => {
    if (!currentId || !ack.checked) return;
    acknowledged = true;
    ack.disabled = true;
    if (rememberIdentity()) message("acknowledged");
    // Acknowledgment is not reconciliation and never unlocks a paid retry.
  });
  newRequest.addEventListener("click", () => {
    if (!allowNew || busy) return;
    stopPolling();
    generation += 1;
    forgetIdentity();
    currentId = null;
    sentOnce = false;
    acknowledged = false;
    polls = 0;
    newAvailable(false);
    hideAck();
    figure.hidden = true;
    preview.removeAttribute("src");
    open.hidden = true;
    open.removeAttribute("href");
    announce(null);
    prompt.value = "";
    consent.checked = false;
    recover(false); // Re-check active work before permitting a new submission.
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stopTimer();
    else schedule();
  });
  window.addEventListener("offline", stopTimer);
  window.addEventListener("online", () => {
    if (recovering && !currentId) recover();
    else schedule();
  });
  window.addEventListener("pagehide", stopTimer);
  window.addEventListener("pageshow", schedule);
  recover();
})();
