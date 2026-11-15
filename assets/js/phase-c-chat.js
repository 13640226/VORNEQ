/* VORNEQ Phase C — development-only, in-memory, independent-turn chat.
 * No localStorage, cookies for chat history, third-party scripts, markdown HTML,
 * model tools, or direct browser-to-provider requests. Source URLs are rechecked.
 */
(() => {
  "use strict";

  function start() {
    const root = document.querySelector("[data-vq-chat]");
    if (!root) return;
    const form = root.querySelector("[data-vq-chat-form]");
    const input = root.querySelector("[data-vq-chat-input]");
    const log = root.querySelector("[data-vq-chat-log]");
    const status = root.querySelector("[data-vq-chat-status]");
    const send = root.querySelector("[data-vq-chat-send]");
    const clear = root.querySelector("[data-vq-chat-clear]");
    const count = root.querySelector("[data-vq-chat-count]");
    const token = form && form.querySelector('input[name="csrfmiddlewaretoken"]');
    if (!form || !input || !log || !status || !send || !clear || !token) return;

    const labels = {
      loading: root.dataset.vqLoading,
      error: root.dataset.vqError,
      empty: root.dataset.vqEmpty,
      sources: root.dataset.vqSources,
      status: root.dataset.vqStatus,
      timeout: root.dataset.vqTimeout,
      recoveryChecking: root.dataset.vqRecoveryChecking,
      recoveryUncertain: root.dataset.vqRecoveryUncertain,
      recoveryExpired: root.dataset.vqRecoveryExpired,
    };
    const language = ["fa", "de", "en"].includes(root.dataset.vqLanguage)
      ? root.dataset.vqLanguage : "en";
    // Prefer the script of the question over the surrounding UI language.
    // Mixed Latin brand names (e.g. VORNEQ) must not override Persian text.
    function questionLanguage(question) {
      if (/[\u0600-\u06FF]/u.test(question)) return "fa";
      if (/[äöüßÄÖÜ]/u.test(question) ||
          /\b(was|wie|warum|welche|welcher|welches|ist|sind|kann|über)\b/iu.test(question)) return "de";
      if (/\b(what|how|why|which|where|is|are|can|does)\b/iu.test(question)) return "en";
      return language;
    }
    function textDirection(text) {
      return /[\u0600-\u06FF]/u.test(text) ? "rtl" : "ltr";
    }
    const limit = 200;
    const recoveryEnabled = root.dataset.vqRecoveryEnabled === "true";
    const recoveryEndpoint = root.dataset.vqRecoveryEndpoint || "";
    const recoveryKey = "vq-ai-chat-recovery-v1";
    let busy = false;
    let recoveryBlocked = false;

    function update() {
      if (count) count.textContent = String(input.value.length) + "/" + limit;
      send.disabled = busy || recoveryBlocked || !input.value.trim();
      clear.disabled = busy;
      input.disabled = busy;
    }
    function appendMessage(text, role) {
      const entry = document.createElement("article");
      entry.className = "vq-chat__message vq-chat__message--" + role;
      entry.dir = textDirection(String(text || ""));
      const p = document.createElement("p");
      p.textContent = String(text || "");
      entry.appendChild(p);
      log.appendChild(entry);
      return entry;
    }
    function relativeUrl(value) {
      if (typeof value !== "string" || !value.startsWith("/") ||
          value.startsWith("//") || value.includes("\\")) return null;
      try {
        const candidate = new URL(value, window.location.origin);
        return candidate.origin === window.location.origin ? candidate.pathname + candidate.search : null;
      } catch (_error) { return null; }
    }
    // Global AI: absolute links only for the server-declared public source
    // hosts (https, no credentials/port, /wiki/ path). Anything else stays text.
    const sourceHosts = new Set(String(root.dataset.vqSourceHosts || "")
      .split(/\s+/).filter((host) => /^[a-z0-9.-]{1,100}$/.test(host)));
    function externalUrl(value) {
      if (typeof value !== "string" || value.length > 400 || !sourceHosts.size) return null;
      try {
        const candidate = new URL(value);
        if (candidate.protocol !== "https:" || !sourceHosts.has(candidate.hostname) ||
            candidate.port || candidate.username || candidate.password ||
            !candidate.pathname.startsWith("/wiki/") || candidate.search || candidate.hash) return null;
        return candidate.href;
      } catch (_error) { return null; }
    }
    function showSources(container, citations) {
      if (!Array.isArray(citations) || !citations.length) return;
      const title = document.createElement("strong");
      title.textContent = labels.sources || "Sources";
      container.appendChild(title);
      const list = document.createElement("ul");
      list.className = "vq-chat__sources";
      for (const source of citations.slice(0, 3)) {
        if (!source || typeof source !== "object") continue;
        const li = document.createElement("li");
        li.dir = textDirection(String(source.title || ""));
        const titleText = String(source.title || source.source_key || source.source_id || "Source").slice(0, 140);
        const href = relativeUrl(source.url);
        const external = href ? null : externalUrl(source.url);
        if (href || external) {
          const link = document.createElement("a");
          link.href = href || external;
          link.rel = external ? "noopener noreferrer external" : "noopener noreferrer";
          if (external) link.target = "_blank";
          link.textContent = titleText;
          li.appendChild(link);
        } else {
          li.textContent = titleText;
        }
        if (typeof source.publisher === "string" && source.publisher) {
          const publisher = document.createElement("span");
          publisher.className = "vq-chat__publisher";
          publisher.textContent = " — " + source.publisher.slice(0, 60);
          li.appendChild(publisher);
        }
        // A verbatim quote checked by the server against this source's excerpt.
        // Treat it as untrusted text, never as HTML or factual verification.
        if (typeof source.evidence_quote === "string" && source.evidence_quote.length >= 8 &&
            source.evidence_quote.length <= 300) {
          const quote = document.createElement("blockquote");
          quote.className = "vq-chat__quote";
          quote.dir = textDirection(source.evidence_quote);
          quote.textContent = source.evidence_quote;
          li.appendChild(quote);
        }
        list.appendChild(li);
      }
      container.appendChild(list);
    }

    // Only an opaque UUID and timestamp are kept in tab-scoped storage; no prompt,
    // answer, citation, credentials, or user ID is stored in the browser.
    function savedRecovery() {
      if (!recoveryEnabled) return null;
      try {
        const raw = window.sessionStorage.getItem(recoveryKey);
        if (!raw) return null;
        const value = JSON.parse(raw);
        if (!value || typeof value.id !== "string" ||
            !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value.id) ||
            typeof value.created !== "number" ||
            Date.now() - value.created > 86400000 || value.created > Date.now() + 60000) {
          window.sessionStorage.removeItem(recoveryKey);
          return null;
        }
        return value;
      } catch (_error) {
        return null;
      }
    }
    function saveRecovery(value) {
      if (!recoveryEnabled) return true;
      try {
        window.sessionStorage.setItem(recoveryKey, JSON.stringify(value));
        return window.sessionStorage.getItem(recoveryKey) === JSON.stringify(value);
      } catch (_error) { return false; }
    }
    function clearRecovery() {
      if (!recoveryEnabled) return;
      try { window.sessionStorage.removeItem(recoveryKey); } catch (_error) { /* no secrets */ }
    }
    function renderData(data) {
      if (data && data.mode === "insufficient_evidence" &&
          data.verified === false && data.model_status === "not_called" &&
          data.grounded_status === "insufficient_evidence" &&
          data.error_code === "INSUFFICIENT_EVIDENCE" &&
          data.answer === "" && Array.isArray(data.citations) &&
          data.citations.length === 0) {
        appendMessage(labels.empty || "Insufficient evidence", "assistant");
        return { completed: true, answerBubble: null };
      }
      if (!data || data.verified !== false ||
          typeof data.answer !== "string" || data.answer.length > 1000 ||
          data.mode !== "grounded_draft" || !Array.isArray(data.citations)) {
        appendMessage(labels.error || "Invalid response", "assistant");
        return { completed: false, answerBubble: null };
      }
      const bubble = appendMessage(data.answer, "assistant");
      const note = document.createElement("small");
      note.textContent = labels.status || "Generated draft, not verified";
      bubble.appendChild(note);
      showSources(bubble, data.citations);
      return { completed: true, answerBubble: bubble };
    }
    function focusAnswer(bubble) {
      if (bubble && typeof bubble.scrollIntoView === "function") {
        const reduce = window.matchMedia &&
          window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        bubble.scrollIntoView({ block: "start", behavior: reduce ? "auto" : "smooth" });
      } else {
        log.scrollTop = log.scrollHeight;
      }
    }
    async function pollRecovery(record) {
      // GET only. This function must NEVER send a POST or create an AI reservation.
      if (!recoveryEnabled || !recoveryEndpoint) return { completed: false, answerBubble: null };
      for (let attempt = 0; attempt < 80; attempt++) {
        try {
          const url = new URL(recoveryEndpoint, window.location.origin);
          if (url.origin !== window.location.origin) throw new Error("invalid origin");
          url.searchParams.set("request_id", record.id);
          const response = await fetch(url.pathname + url.search, {
            method: "GET", credentials: "same-origin", cache: "no-store",
            redirect: "error", headers: { "Accept": "application/json" },
          });
          if (!response.ok) throw new Error("status unavailable");
          const data = await response.json();
          if (data.status === "running") {
            status.textContent = labels.recoveryChecking || "Checking previous request…";
            await new Promise((resolve) => window.setTimeout(resolve, 1250));
            continue;
          }
          if (data.status === "completed" && data.http_status === 200) {
            const rendered = renderData(data.response);
            if (!rendered.completed) recoveryBlocked = true;
            return rendered;
          }
          if (data.status === "failed" && data.http_status === 422 &&
              data.response && (data.response.error === "UNSUPPORTED_QUESTION" ||
              data.response.error === "INSUFFICIENT_EVIDENCE")) {
            appendMessage(labels.empty || "Insufficient evidence", "assistant");
            return { completed: true, answerBubble: null };
          }
          if (data.status === "completed" || data.status === "failed") {
            appendMessage(labels.error || "Request could not be displayed", "assistant");
            recoveryBlocked = true;
            return { completed: false, answerBubble: null };
          }
          if (data.status === "expired") {
            clearRecovery();
            appendMessage(labels.recoveryExpired || "Previous answer is no longer available.", "assistant");
            return { completed: false, answerBubble: null };
          }
          if (data.status === "uncertain") {
            recoveryBlocked = true;
            appendMessage(labels.recoveryUncertain || "Request status uncertain; do not resubmit.", "assistant");
            return { completed: false, answerBubble: null };
          }
          throw new Error("invalid recovery response");
        } catch (_error) {
          recoveryBlocked = true;
          appendMessage(labels.recoveryUncertain || labels.timeout || "Unable to recover. Do not resubmit.", "assistant");
          return { completed: false, answerBubble: null };
        }
      }
      recoveryBlocked = true;
      appendMessage(labels.recoveryUncertain || labels.timeout || "Unable to recover. Do not resubmit.", "assistant");
      return { completed: false, answerBubble: null };
    }
    async function restoreRecovery() {
      const saved = savedRecovery();
      if (!saved) return;
      busy = true;
      form.setAttribute("aria-busy", "true");
      update();
      status.textContent = labels.recoveryChecking || "Checking previous request…";
      try {
        const result = await pollRecovery(saved);
        focusAnswer(result.answerBubble);
      } finally {
        status.textContent = "";
        form.removeAttribute("aria-busy");
        busy = false;
        update();
      }
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (busy || recoveryBlocked) return;
      const question = input.value.trim().slice(0, limit);
      if (!question) { input.focus(); return; }
      let requestId = null;
      if (recoveryEnabled) {
        // The request ID is persisted BEFORE the potentially billable POST.
        if (!window.crypto || typeof window.crypto.randomUUID !== "function") {
          appendMessage(labels.recoveryUncertain || labels.error, "assistant");
          recoveryBlocked = true;
          update();
          return;
        }
        requestId = window.crypto.randomUUID();
        if (!saveRecovery({ id: requestId, created: Date.now() })) {
          appendMessage(labels.recoveryUncertain || labels.error, "assistant");
          recoveryBlocked = true;
          update();
          return;
        }
      }
      busy = true;
      update();
      form.setAttribute("aria-busy", "true");
      status.textContent = labels.loading || "Loading";
      appendMessage(question, "user");
      let answerBubble = null;
      let completed = false;
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 35000);
      try {
        const headers = {
          "Content-Type": "application/json",
          "Accept": "application/json",
          "X-CSRFToken": token.value,
        };
        if (requestId) headers["X-VQ-Request-ID"] = requestId;
        const response = await fetch(form.action, {
          method: "POST",
          credentials: "same-origin",
          cache: "no-store",
          redirect: "error",
          headers,
          body: JSON.stringify({ question, language: questionLanguage(question) }),
          signal: controller.signal,
        });
        if (requestId && response.status === 202) {
          const state = await pollRecovery({ id: requestId });
          completed = state.completed;
          answerBubble = state.answerBubble;
        } else if (response.status === 422) {
          appendMessage(labels.empty || "Insufficient evidence", "assistant");
          completed = true;
        } else if (!response.ok) {
          appendMessage(labels.error || "Request failed", "assistant");
          if (requestId) recoveryBlocked = true;
        } else {
          const data = await response.json();
          const rendered = renderData(data);
          completed = rendered.completed;
          answerBubble = rendered.answerBubble;
          if (!completed && requestId) recoveryBlocked = true;
        }
      } catch (error) {
        // An aborted browser fetch does not cancel or refund the provider.
        const timedOut = error && error.name === "AbortError";
        appendMessage(timedOut ? (labels.timeout || labels.error || "Request timed out") :
          (labels.error || "Request failed"), "assistant");
        if (requestId) recoveryBlocked = true;
      } finally {
        window.clearTimeout(timeout);
        status.textContent = "";
        if (completed) input.value = "";
        form.removeAttribute("aria-busy");
        busy = false;
        update();
        input.focus({ preventScroll: true });
        focusAnswer(answerBubble);
      }
    });
    clear.addEventListener("click", () => {
      if (busy) return;
      log.replaceChildren();
      clearRecovery();
      recoveryBlocked = false;
      input.value = "";
      status.textContent = "";
      update();
      input.focus();
    });
    input.addEventListener("input", update);
    input.addEventListener("keydown", (event) => {
      if (event.isComposing || event.keyCode === 229) return;
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        if (form.requestSubmit) form.requestSubmit();
      }
    });
    update();
    if (recoveryEnabled) restoreRecovery();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else { start(); }
})();
