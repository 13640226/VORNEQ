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
    let busy = false;

    function update() {
      if (count) count.textContent = String(input.value.length) + "/" + limit;
      send.disabled = busy || !input.value.trim();
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

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (busy) return;
      const question = input.value.trim().slice(0, limit);
      if (!question) { input.focus(); return; }
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
        const response = await fetch(form.action, {
          method: "POST",
          credentials: "same-origin",
          cache: "no-store",
          redirect: "error",
          headers: {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-CSRFToken": token.value,
          },
          body: JSON.stringify({ question, language: questionLanguage(question) }),
          signal: controller.signal,
        });
        if (response.status === 422) {
          appendMessage(labels.empty || "Insufficient evidence", "assistant");
          completed = true;
        } else if (!response.ok) {
          appendMessage(labels.error || "Request failed", "assistant");
        } else {
          const data = await response.json();
          if (data && data.mode === "insufficient_evidence" &&
              data.verified === false && data.model_status === "not_called" &&
              data.grounded_status === "insufficient_evidence" &&
              data.error_code === "INSUFFICIENT_EVIDENCE" &&
              data.answer === "" && Array.isArray(data.citations) &&
              data.citations.length === 0) {
            appendMessage(labels.empty || "Insufficient evidence", "assistant");
            completed = true;
          } else if (!data || data.verified !== false ||
              typeof data.answer !== "string" || data.answer.length > 1000 ||
              data.mode !== "grounded_draft" || !Array.isArray(data.citations)) {
            appendMessage(labels.error || "Invalid response", "assistant");
          } else {
            const bubble = appendMessage(data.answer, "assistant");
            const note = document.createElement("small");
            note.textContent = labels.status || "Generated draft, not verified";
            bubble.appendChild(note);
            showSources(bubble, data.citations);
            answerBubble = bubble;
            completed = true;
          }
        }
      } catch (error) {
        // The provider might have finished even if this browser timed out;
        // warn before retry to avoid charging for a duplicate request.
        const timedOut = error && error.name === "AbortError";
        appendMessage(timedOut ? (labels.timeout || labels.error || "Request timed out") :
          (labels.error || "Request failed"), "assistant");
      } finally {
        window.clearTimeout(timeout);
        status.textContent = "";
        if (completed) input.value = "";
        form.removeAttribute("aria-busy");
        busy = false;
        update();
        input.focus({ preventScroll: true });
        // Show the START of the answer so its sources are not hidden below a
        // nested scroll position (mobile citation discoverability).
        if (answerBubble && typeof answerBubble.scrollIntoView === "function") {
          const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
          answerBubble.scrollIntoView({ block: "start", behavior: reduce ? "auto" : "smooth" });
        } else {
          log.scrollTop = log.scrollHeight;
        }
      }
    });
    clear.addEventListener("click", () => {
      if (busy) return;
      log.replaceChildren();
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
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else { start(); }
})();
