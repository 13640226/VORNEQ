/* VORNEQ AI chat. Without the conversations flag every question is independent.
 * With persistent conversations V1, history lives only on the server; the browser
 * keeps no chat content (no localStorage, no chat cookies). No third-party scripts,
 * markdown HTML, model tools, or direct browser-to-provider requests. Source URLs
 * are rechecked.
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
      unsupported: root.dataset.vqUnsupported,
      rejectedEvidence: root.dataset.vqRejectedEvidence,
      rejectedOutput: root.dataset.vqRejectedOutput,
      citationIdentity: root.dataset.vqCitationIdentity,
      citationDigest: root.dataset.vqCitationDigest,
      citationQuote: root.dataset.vqCitationQuote,
      unsupportedNumber: root.dataset.vqUnsupportedNumber,
      sources: root.dataset.vqSources,
      status: root.dataset.vqStatus,
      timeout: root.dataset.vqTimeout,
      recoveryChecking: root.dataset.vqRecoveryChecking,
      recoveryUncertain: root.dataset.vqRecoveryUncertain,
      recoveryExpired: root.dataset.vqRecoveryExpired,
      you: root.dataset.vqYou,
      assistant: root.dataset.vqAssistant,
      copy: root.dataset.vqCopy,
      copied: root.dataset.vqCopied,
    };
    // Example prompts only fill the box. They never submit: every request may be billable.
    const welcome = root.querySelector("[data-vq-chat-welcome]");
    for (const example of root.querySelectorAll("[data-vq-chat-example]")) {
      example.addEventListener("click", () => {
        if (busy) return;
        const exampleQuestion = String(example.textContent || "").trim();
        if (!fitsQuestion(exampleQuestion)) return;
        input.value = exampleQuestion;
        update();
        input.focus();
      });
    }
    const language = ["fa", "de", "en"].includes(root.dataset.vqLanguage)
      ? root.dataset.vqLanguage : "en";
    // Trusted template values, bounded to the existing server policy.
    const rawAnswerLimit = Number(root.dataset.vqAnswerLimit);
    const answerLimit = Number.isInteger(rawAnswerLimit) && rawAnswerLimit >= 1000 &&
      rawAnswerLimit <= 2400 ? rawAnswerLimit : 1000;
    const citationLimit = root.dataset.vqCitationLimit === "5" ? 5 : 3;
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
    const rawLimit = Number(root.dataset.vqQuestionLimit);
    const limit = Number.isInteger(rawLimit) && rawLimit >= 200 && rawLimit <= 8192 ? rawLimit : 200;
    const rawBytes = Number(root.dataset.vqQuestionBytes);
    const byteLimit = Number.isInteger(rawBytes) && rawBytes === limit && rawBytes >= 512 ? rawBytes : 0;
    function inputCount(value) {
      return byteLimit ? new TextEncoder().encode(value).length : Array.from(value).length;
    }
    function fitsQuestion(value) {
      return Array.from(value).length <= limit && inputCount(value) <= (byteLimit || limit);
    }
    const recoveryEnabled = root.dataset.vqRecoveryEnabled === "true";
    const recoveryEndpoint = root.dataset.vqRecoveryEndpoint || "";
    const recoveryKey = "vq-ai-chat-recovery-v1";
    let busy = false;
    let recoveryBlocked = false;

    function update() {
      if (count) count.textContent = String(inputCount(input.value)) + "/" + (byteLimit || limit) + (byteLimit ? " B" : "");
      send.disabled = busy || recoveryBlocked || !input.value.trim() || !fitsQuestion(input.value);
      clear.disabled = busy;
      input.disabled = busy;
      root.classList.toggle("vq-chat--busy", busy);
    }
    function appendMessage(text, role) {
      const entry = document.createElement("article");
      entry.className = "vq-chat__message vq-chat__message--" + role;
      entry.dir = textDirection(String(text || ""));
      const author = document.createElement("span");
      author.className = "vq-chat__author";
      author.textContent = (role === "user" ? labels.you : labels.assistant) || "";
      entry.appendChild(author);
      const p = document.createElement("p");
      p.textContent = String(text || "");
      entry.appendChild(p);
      log.appendChild(entry);
      if (welcome) welcome.hidden = true;
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
      for (const source of citations.slice(0, citationLimit)) {
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
        if (Array.isArray(source.passages) && source.passages.length <= 8) {
          const passages = document.createElement("ul");
          passages.className = "vq-chat__passages";
          for (const p of source.passages) {
            if (!p || typeof p !== "object" || typeof p.quote !== "string" ||
                p.quote.length > 300 || typeof p.passage_id !== "string" ||
                !/^S[1-5]\.P[1-9][0-9]?$/.test(p.passage_id)) continue;
            const item = document.createElement("li");
            item.dir = textDirection(p.quote);
            const id = document.createElement("strong");
            id.textContent = p.passage_id;
            item.appendChild(id);
            const quote = document.createElement("blockquote");
            quote.textContent = p.quote;
            item.appendChild(quote);
            passages.appendChild(item);
          }
          if (passages.childElementCount) li.appendChild(passages);
        }
        list.appendChild(li);
      }
      container.appendChild(list);
    }

    function renderSections(bubble, sections) {
      if (!Array.isArray(sections) || sections.length < 1 || sections.length > 6) return;
      const rootSections = document.createElement("div");
      rootSections.className = "vq-chat__sections";
      for (const section of sections) {
        if (!section || !["answer", "gap"].includes(section.kind) ||
            typeof section.text !== "string" || section.text.length > 700 ||
            typeof section.heading !== "string" || section.heading.length > 80) return;
        const block = document.createElement("section");
        block.className = "vq-chat__section";
        block.dir = textDirection(section.text);
        if (section.heading) {
          const heading = document.createElement("h3");
          heading.textContent = section.heading;
          block.appendChild(heading);
        }
        const p = document.createElement("p");
        p.textContent = section.text;
        block.appendChild(p);
        if (Array.isArray(section.refs) && section.refs.length <= 4 &&
            section.refs.every((ref) => typeof ref === "string" && /^S[1-5]\.P[1-9][0-9]?$/.test(ref))) {
          const ids = document.createElement("small");
          ids.className = "vq-chat__section-refs";
          ids.textContent = section.refs.join(" · ");
          block.appendChild(ids);
        }
        rootSections.appendChild(block);
      }
      // The flat string always remains the fallback, including DB replay.
      const original = bubble.querySelector("p");
      if (original && rootSections.childElementCount) {
        original.hidden = true;
        bubble.insertBefore(rootSections, original.nextSibling);
      }
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
    // Only fixed server error enums are recognized. Never render server-supplied
    // reason text, prompt, model output or exception messages in failure bubbles.
    function rejectionMessage(data) {
      if (!data || typeof data !== "object") return labels.error || "Request failed";
      if (data.error === "UNSUPPORTED_QUESTION") {
        return labels.unsupported || "Question unsupported; no model request was sent.";
      }
      if (data.error === "provider_unavailable" &&
          data.reason_code === "invalid_provider_response") {
        return labels.rejectedOutput || labels.error || "Request failed";
      }
      if (data.error !== "INSUFFICIENT_EVIDENCE") {
        return labels.error || "Request failed";
      }
      const safeReasons = Object.freeze({
        invalid_generated_output: labels.rejectedOutput,
        citation_identity_rejected: labels.citationIdentity,
        citation_digest_mismatch: labels.citationDigest,
        citation_quote_mismatch: labels.citationQuote,
        unsupported_numeric_claim: labels.unsupportedNumber,
        evidence_rejected: labels.rejectedEvidence,
      });
      return Object.prototype.hasOwnProperty.call(safeReasons, data.reason_code)
        ? (safeReasons[data.reason_code] || labels.rejectedEvidence)
        : (labels.rejectedEvidence || "Answer failed evidence checks; check usage before retrying.");
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
          typeof data.answer !== "string" || data.answer.length > answerLimit ||
          data.mode !== "grounded_draft" || !Array.isArray(data.citations)) {
        appendMessage(labels.error || "Invalid response", "assistant");
        return { completed: false, answerBubble: null };
      }
      const bubble = appendMessage(data.answer, "assistant");
      if (data.format_version === 2 && Array.isArray(data.sections)) {
        renderSections(bubble, data.sections);
      }
      const note = document.createElement("small");
      note.textContent = labels.status || "Generated draft, not verified";
      bubble.appendChild(note);
      showSources(bubble, data.citations);
      addCopyButton(bubble, data.answer);
      return { completed: true, answerBubble: bubble };
    }
    // Copies only the plain answer text that is already displayed.
    function addCopyButton(bubble, answer) {
      if (!navigator.clipboard || typeof navigator.clipboard.writeText !== "function") return;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "vq-chat__copy";
      button.textContent = labels.copy || "Copy";
      button.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(String(answer));
          button.textContent = labels.copied || "Copied";
          window.setTimeout(() => { button.textContent = labels.copy || "Copy"; }, 2000);
        } catch (_error) { /* clipboard permission denied: leave the text selectable */ }
      });
      bubble.appendChild(button);
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
            appendMessage(rejectionMessage(data.response), "assistant");
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

    // Persistent conversations V1: history lives on the server (PostgreSQL),
    // never in browser storage. Only an opaque conversation UUID is in the URL.
    const conv = root.dataset.vqConversations === "true" ? setupConversations() : null;
    function setupConversations() {
      const endpoint = root.dataset.vqConvEndpoint || "";
      const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
      if (!endpoint.startsWith("/") || endpoint.startsWith("//")) return null;
      const panel = document.querySelector("[data-vq-conv-panel]");
      const items = document.querySelector("[data-vq-conv-items]");
      const emptyNote = document.querySelector("[data-vq-conv-empty]");
      const search = document.querySelector("[data-vq-conv-search]");
      const newButton = document.querySelector("[data-vq-conv-new]");
      const trashButton = document.querySelector("[data-vq-conv-trash]");
      const modeNote = document.querySelector("[data-vq-conv-mode]");
      const bar = root.querySelector("[data-vq-conv-bar]");
      const titleEl = root.querySelector("[data-vq-conv-title]");
      const renameButton = root.querySelector("[data-vq-conv-rename]");
      const renameForm = root.querySelector("[data-vq-conv-rename-form]");
      const titleInput = root.querySelector("[data-vq-conv-title-input]");
      const archiveButton = root.querySelector("[data-vq-conv-archive]");
      const exportLink = root.querySelector("[data-vq-conv-export]");
      const deleteButton = root.querySelector("[data-vq-conv-delete]");
      if (!items || !newButton || !bar || !titleEl) return null;
      let current = null;
      let trashMode = false;
      let searchTimer = null;
      const initial = new URL(window.location.href).searchParams.get("c");
      let activeId = initial && uuidPattern.test(initial) ? initial : null;

      async function api(method, url, body) {
        const headers = { "Accept": "application/json", "X-CSRFToken": token.value };
        const options = { method, headers, credentials: "same-origin", cache: "no-store", redirect: "error" };
        if (body !== undefined) {
          headers["Content-Type"] = "application/json";
          options.body = JSON.stringify(body);
        }
        const response = await fetch(url, options);
        let data = null;
        try { data = await response.json(); } catch (_error) { data = null; }
        return { ok: response.ok, status: response.status, data };
      }
      function detailUrl(id) { return endpoint + id + "/"; }
      function setUrl(id) {
        const url = new URL(window.location.href);
        if (id) url.searchParams.set("c", id); else url.searchParams.delete("c");
        window.history.replaceState(null, "", url.pathname + url.search);
      }
      function showBar(conversation) {
        current = conversation;
        bar.hidden = !conversation;
        if (!conversation) return;
        titleEl.textContent = conversation.title || root.dataset.vqConvUntitled || "";
        titleEl.dir = textDirection(titleEl.textContent);
        if (archiveButton) {
          archiveButton.textContent = conversation.archived
            ? archiveButton.dataset.labelUnarchive : archiveButton.dataset.labelArchive;
        }
        if (exportLink) exportLink.href = detailUrl(conversation.id) + "export/";
      }
      function renderStored(messages) {
        log.replaceChildren();
        if (welcome) welcome.hidden = messages.length > 0;
        for (const message of messages) {
          if (!message || typeof message !== "object") continue;
          if (message.role === "user") {
            appendMessage(String(message.content || ""), "user");
          } else if (message.status === "completed") {
            renderData({ mode: "grounded_draft", verified: false, answer: String(message.content || ""),
              citations: Array.isArray(message.citations) ? message.citations : [] });
          } else if (message.status === "insufficient_evidence") {
            const code = String(message.error_code || "");
            if (code === "UNSUPPORTED_QUESTION") appendMessage(rejectionMessage({ error: code }), "assistant");
            else if (code === "insufficient_evidence" || code === "INSUFFICIENT_EVIDENCE") appendMessage(labels.empty || "", "assistant");
            else appendMessage(rejectionMessage({ error: "INSUFFICIENT_EVIDENCE", reason_code: code }), "assistant");
          } else {
            appendMessage(labels.error || "Request failed", "assistant");
          }
        }
      }
      function renderList(conversations) {
        items.replaceChildren();
        if (emptyNote) emptyNote.hidden = conversations.length > 0;
        for (const item of conversations) {
          if (!item || !uuidPattern.test(String(item.id))) continue;
          const li = document.createElement("li");
          li.className = "vq-chat__history-item";
          const title = String(item.title || root.dataset.vqConvUntitled || "");
          if (trashMode) {
            const name = document.createElement("span");
            name.className = "vq-chat__history-name";
            name.textContent = title;
            name.dir = textDirection(title);
            const restore = document.createElement("button");
            restore.type = "button";
            restore.textContent = root.dataset.vqConvRestore || "Restore";
            restore.addEventListener("click", async () => {
              const result = await api("POST", detailUrl(item.id) + "restore/");
              if (result.ok) refreshList();
            });
            const forever = document.createElement("button");
            forever.type = "button";
            forever.textContent = root.dataset.vqConvDeleteForever || "Delete forever";
            forever.addEventListener("click", async () => {
              if (!window.confirm(root.dataset.vqConvDeleteForeverConfirm || "Delete forever?")) return;
              const result = await api("DELETE", detailUrl(item.id) + "?permanent=1");
              if (result.ok) refreshList();
            });
            li.append(name, restore, forever);
          } else {
            const open = document.createElement("button");
            open.type = "button";
            open.className = "vq-chat__history-open";
            open.textContent = title;
            open.dir = textDirection(title);
            if (item.id === activeId) open.setAttribute("aria-current", "true");
            open.addEventListener("click", () => { if (!busy) openConversation(item.id); });
            li.appendChild(open);
          }
          items.appendChild(li);
        }
      }
      async function refreshList() {
        const url = new URL(endpoint, window.location.origin);
        if (trashMode) url.searchParams.set("trash", "1");
        const query = search ? search.value.trim().slice(0, 100) : "";
        if (query) url.searchParams.set("q", query);
        try {
          const result = await api("GET", url.pathname + url.search);
          if (result.ok && result.data && Array.isArray(result.data.conversations)) renderList(result.data.conversations);
        } catch (_error) { /* the list is a convenience; the chat keeps working */ }
      }
      async function openConversation(id) {
        if (!uuidPattern.test(String(id))) return false;
        try {
          const result = await api("GET", detailUrl(id));
          if (!result.ok || !result.data || !Array.isArray(result.data.messages)) {
            if (result.status === 404) { startNew(); return false; }
            status.textContent = root.dataset.vqConvLoadError || labels.error || "";
            return false;
          }
          activeId = id;
          setUrl(id);
          showBar(result.data.conversation);
          renderStored(result.data.messages);
          refreshList();
          if (panel && window.matchMedia && window.matchMedia("(max-width: 1023px)").matches) panel.open = false;
          return result.data.messages;
        } catch (_error) {
          status.textContent = root.dataset.vqConvLoadError || labels.error || "";
          return false;
        }
      }
      function startNew() {
        activeId = null;
        setUrl(null);
        showBar(null);
        log.replaceChildren();
        if (welcome) welcome.hidden = false;
        refreshList();
      }
      async function ensure(question) {
        if (activeId) return true;
        const result = await api("POST", endpoint, { language: questionLanguage(question), title: question });
        if (!result.ok || !result.data || !result.data.conversation ||
            !uuidPattern.test(String(result.data.conversation.id))) {
          appendMessage(result.status === 409 ? (root.dataset.vqConvFull || labels.error) : (labels.error || ""), "assistant");
          return false;
        }
        activeId = result.data.conversation.id;
        setUrl(activeId);
        showBar(result.data.conversation);
        return true;
      }
      newButton.addEventListener("click", () => { if (!busy) { startNew(); input.focus(); } });
      if (search) search.addEventListener("input", () => {
        window.clearTimeout(searchTimer);
        searchTimer = window.setTimeout(refreshList, 250);
      });
      if (trashButton) trashButton.addEventListener("click", () => {
        trashMode = !trashMode;
        trashButton.textContent = trashMode ? trashButton.dataset.labelBack : trashButton.dataset.labelTrash;
        if (modeNote) modeNote.hidden = !trashMode;
        refreshList();
      });
      if (renameButton && renameForm && titleInput) {
        renameButton.addEventListener("click", () => {
          if (!current) return;
          titleInput.value = current.title || "";
          renameForm.hidden = false;
          titleInput.focus();
        });
        renameForm.addEventListener("submit", async (event) => {
          event.preventDefault();
          const title = titleInput.value.trim().slice(0, 120);
          if (!current || !title) return;
          const result = await api("PATCH", detailUrl(current.id), { title });
          if (result.ok && result.data) showBar(result.data.conversation);
          renameForm.hidden = true;
          refreshList();
        });
      }
      if (archiveButton) archiveButton.addEventListener("click", async () => {
        if (!current) return;
        const result = await api("PATCH", detailUrl(current.id), { archived: !current.archived });
        if (result.ok && result.data) { showBar(result.data.conversation); refreshList(); }
      });
      if (deleteButton) deleteButton.addEventListener("click", async () => {
        if (!current || busy) return;
        if (!window.confirm(root.dataset.vqConvDeleteConfirm || "Delete?")) return;
        const result = await api("DELETE", detailUrl(current.id));
        if (result.ok) startNew();
      });
      async function init() {
        const saved = savedRecovery();
        const messages = activeId ? await openConversation(activeId) : (refreshList(), []);
        if (!saved) return;
        const stored = Array.isArray(messages) && messages.some((m) => m && m.request_id === saved.id);
        if (stored) { clearRecovery(); return; }
        // An in-flight request from before the reload: poll (GET only), then reload history.
        await restoreRecovery();
        if (activeId) await openConversation(activeId);
      }
      return {
        ensure,
        init,
        startNew,
        refresh: refreshList,
        messagesUrl: () => detailUrl(activeId) + "messages/",
        fullLabel: () => root.dataset.vqConvFull || labels.error || "",
      };
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (busy || recoveryBlocked) return;
      const question = input.value.trim();
      if (!question || !fitsQuestion(input.value)) { input.focus(); return; }
      // Conversation mode: create the (cost-free) conversation before any billable request.
      if (conv) {
        busy = true;
        update();
        let ready = false;
        try { ready = await conv.ensure(question); } catch (_error) { ready = false; }
        busy = false;
        update();
        if (!ready) return;
      }
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
        const response = await fetch(conv ? conv.messagesUrl() : form.action, {
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
          const failure = await response.json();
          appendMessage(rejectionMessage(failure), "assistant");
          completed = true;
        } else if (conv && response.status === 409) {
          appendMessage(conv.fullLabel(), "assistant");
          if (requestId) clearRecovery();
        } else if (!response.ok) {
          // A failed provider parse may follow a billable HTTP 200. Show only a
          // fixed localized explanation; never auto-retry the original request.
          let failure = null;
          if (response.status === 503) {
            try { failure = await response.json(); } catch (_error) { /* fail closed */ }
          }
          appendMessage(rejectionMessage(failure), "assistant");
          if (requestId) recoveryBlocked = true;
        } else {
          const data = await response.json();
          const rendered = renderData(data);
          completed = rendered.completed;
          answerBubble = rendered.answerBubble;
          // Conversation mode: never imply the answer is in the history if it is not.
          if (conv && data && data.persisted === false) {
            appendMessage(root.dataset.vqConvNotSaved || labels.error || "", "assistant");
          }
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
        if (conv) {
          if (completed) clearRecovery();
          conv.refresh();
        }
      }
    });
    clear.addEventListener("click", () => {
      if (busy) return;
      if (conv) { clearRecovery(); recoveryBlocked = false; input.value = ""; status.textContent = "";
        conv.startNew(); update(); input.focus(); return; }
      log.replaceChildren();
      if (welcome) welcome.hidden = false;
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
    if (conv) conv.init();
    else if (recoveryEnabled) restoreRecovery();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else { start(); }
})();
