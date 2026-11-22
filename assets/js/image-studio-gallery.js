/* VORNEQ Image Studio gallery, toolbar and viewer.
 * Strictly GET-only: history, signed-URL lookups and same-origin PNG downloads.
 * Independent of the PR 1 generation state in image-studio.js: it only listens to the
 * completion event and never reads or writes job UUIDs, polling or acknowledgments.
 * Signed URLs live in a small in-memory cache and are never persisted.
 */
(() => {
  "use strict";

  const root = document.querySelector("[data-vq-image-studio]");
  const gallery = document.querySelector("[data-vq-gallery]");
  if (!root || !gallery) return;
  const createUrl = root.dataset.createUrl;
  const historyUrl = gallery.dataset.historyUrl;
  if (!createUrl || !historyUrl) return;

  let L = {};
  try {
    L = JSON.parse(document.getElementById("vq-image-labels").textContent);
  } catch (_error) { /* Labels fall back to empty text. */ }
  const t = (key, vars) => {
    let text = typeof L[key] === "string" ? L[key] : "";
    if (vars) for (const name of Object.keys(vars)) text = text.replace("{" + name + "}", String(vars[name]));
    return text;
  };

  const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  const sizePattern = /^[0-9]{3,4}x[0-9]{3,4}$/;
  const PAGE_SIZE = 20;
  const GET_TIMEOUT_MS = 15000;
  const FILE_TIMEOUT_MS = 30000;
  const MAX_FILE_BYTES = 12 * 1024 * 1024;
  const MAX_CONCURRENT = 3;
  const MAX_QUEUE = 60;
  const MAX_CACHE = 80;
  const MAX_ITEMS = 500;
  const ZOOM_MIN = 1;
  const ZOOM_MAX = 4;
  const ZOOM_STEP = 0.5;

  const q = (name) => gallery.querySelector("[data-vq-gallery-" + name + "]");
  const statusEl = q("status");
  const grid = q("grid");
  const moreBtn = q("more");
  const retryBtn = q("retry");
  const selectedBox = q("selected");
  const selectedImg = q("selected-img");

  // ---- helpers -----------------------------------------------------------------
  function signedLink(value) {
    if (typeof value !== "string") return null;
    try {
      const candidate = new URL(value);
      if (candidate.protocol !== "https:" || candidate.username || candidate.password) return null;
      return candidate.href;
    } catch (_error) { return null; }
  }

  async function getJson(url, signal) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), GET_TIMEOUT_MS);
    if (signal) signal.addEventListener("abort", () => controller.abort());
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

  const downloadUrl = (id) => createUrl + encodeURIComponent(id) + "/download/";

  async function fetchBlob(id) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), FILE_TIMEOUT_MS);
    try {
      const response = await fetch(downloadUrl(id), {
        method: "GET", credentials: "same-origin", cache: "no-store",
        headers: {"Accept": "image/png"}, signal: controller.signal
      });
      if (response.status !== 200) throw new Error("download");
      const blob = await response.blob();
      if (blob.type !== "image/png" || blob.size < 1 || blob.size > MAX_FILE_BYTES) throw new Error("image");
      return blob;
    } finally {
      clearTimeout(timeout);
    }
  }

  // ---- signed URL cache (memory only, bounded) -----------------------------------
  const urlCache = new Map();
  function cacheSet(id, href) {
    urlCache.delete(id);
    urlCache.set(id, href);
    while (urlCache.size > MAX_CACHE) urlCache.delete(urlCache.keys().next().value);
  }

  async function fetchSigned(id, fresh = false) {
    if (!uuidPattern.test(id)) return null;
    if (!fresh && urlCache.has(id)) {
      const hit = urlCache.get(id);
      cacheSet(id, hit);
      return hit;
    }
    try {
      const result = await getJson(createUrl + encodeURIComponent(id) + "/");
      const job = result.body;
      if (result.status !== 200 || !job || job.id !== id || job.status !== "completed") return null;
      const href = signedLink(job.image_url);
      if (href) cacheSet(id, href);
      return href;
    } catch (_error) { return null; }
  }

  // ---- history list --------------------------------------------------------------
  const known = new Set();
  const cards = new Map();
  let items = [];
  let nextCursor = null;
  let hasMore = false;
  let loading = false;
  let listGen = 0;
  let listController = null;
  let selectedId = null;
  let currentId = null;

  function setStatus(key) {
    statusEl.textContent = key ? t(key) : "";
  }

  function validPage(body) {
    if (!body || !Array.isArray(body.results) || body.results.length > 50) return false;
    if (body.next_cursor !== null && (typeof body.next_cursor !== "string" || body.next_cursor.length > 512)) return false;
    return body.results.every((item) => item && typeof item.id === "string" && uuidPattern.test(item.id)
      && item.status === "completed" && typeof item.size === "string" && sizePattern.test(item.size)
      && typeof item.created_at === "string" && !Number.isNaN(Date.parse(item.created_at)));
  }

  function formatDate(value) {
    try {
      const lang = document.documentElement && document.documentElement.lang;
      return new Date(value).toLocaleString(lang || undefined, {dateStyle: "medium", timeStyle: "short"});
    } catch (_error) { return value; }
  }

  const visible = new Set();
  const queue = [];
  const inflight = new Set();
  let active = 0;
  let observer = null;

  function requestThumb(id) {
    const card = cards.get(id);
    if (!card || card.loaded || inflight.has(id) || queue.includes(id)) return;
    if (queue.length >= MAX_QUEUE) {
      const dropped = queue.shift();
      const old = cards.get(dropped);
      // Visible but unloaded: observe again so it re-enters the queue later.
      if (old && observer) { observer.unobserve(old.node); observer.observe(old.node); }
    }
    queue.push(id);
    pump();
  }

  function pump() {
    while (active < MAX_CONCURRENT && queue.length) {
      const id = queue.shift();
      const card = cards.get(id);
      if (!card || card.loaded || (observer && !visible.has(id))) continue;
      active += 1;
      inflight.add(id);
      fetchSigned(id).then((href) => {
        const current = cards.get(id);
        if (!current || current !== card) return; // list was reset meanwhile
        if (href) { current.img.src = href; } else { fail(current); }
      }).finally(() => {
        active -= 1;
        inflight.delete(id);
        pump();
      });
    }
  }

  function fail(card) {
    card.node.setAttribute("data-failed", "true");
    card.node.title = t("load_failed");
  }

  function buildCard(item) {
    const li = document.createElement("li");
    li.className = "vq-gallery__item";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "vq-gallery__card";
    button.setAttribute("aria-pressed", "false");
    button.setAttribute("aria-label", t("image_card", {date: formatDate(item.created_at)}));
    const img = document.createElement("img");
    img.alt = "";
    img.decoding = "async";
    img.referrerPolicy = "no-referrer";
    const date = document.createElement("span");
    date.className = "vq-gallery__meta";
    date.textContent = formatDate(item.created_at);
    const size = document.createElement("span");
    size.className = "vq-gallery__meta";
    size.textContent = item.size + (item.mock ? " \u00b7 " + t("mock_badge") : "");
    button.append(img, date, size);
    li.append(button);
    const card = {id: item.id, node: button, li, img, loaded: false, retried: false};
    img.addEventListener("load", () => { card.loaded = true; });
    img.addEventListener("error", async () => {
      if (!img.getAttribute("src") || card.retried || cards.get(card.id) !== card) { fail(card); return; }
      card.retried = true; // one signed-URL refresh per card, GET only
      const href = await fetchSigned(card.id, true);
      if (cards.get(card.id) === card && href) img.src = href; else fail(card);
    });
    button.addEventListener("click", () => select(item.id));
    return card;
  }

  function render(newItems, {prepend = false} = {}) {
    const added = [];
    for (const item of newItems) {
      if (known.has(item.id)) continue;
      if (items.length + added.length >= MAX_ITEMS) break;
      known.add(item.id);
      added.push(item);
    }
    if (!added.length) return;
    items = prepend ? added.concat(items) : items.concat(added);
    const nodes = added.map((item) => {
      const card = buildCard(item);
      cards.set(item.id, card);
      return card;
    });
    if (prepend) grid.prepend(...nodes.map((card) => card.li));
    else grid.append(...nodes.map((card) => card.li));
    for (const card of nodes) {
      if (observer) observer.observe(card.node);
      else if (cards.size <= 12) requestThumb(card.id);
    }
  }

  function updateControls() {
    moreBtn.hidden = !(hasMore && !loading);
    retryBtn.hidden = true;
    if (!items.length && !loading) setStatus("gallery_empty");
  }

  async function loadPage({reset = false} = {}) {
    if (loading && !reset) return;
    if (reset) {
      listGen += 1;
      if (listController) listController.abort();
      known.clear(); cards.clear(); items = []; nextCursor = null; hasMore = false;
      visible.clear(); queue.length = 0;
      grid.textContent = "";
    }
    const generation = listGen;
    const controller = new AbortController();
    listController = controller;
    loading = true;
    moreBtn.hidden = true;
    retryBtn.hidden = true;
    setStatus("gallery_loading");
    try {
      let url = historyUrl + "?limit=" + PAGE_SIZE;
      if (nextCursor) url += "&cursor=" + encodeURIComponent(nextCursor);
      const result = await getJson(url, controller.signal);
      if (generation !== listGen) return; // stale before any DOM change
      if (result.status !== 200 || !validPage(result.body)) throw new Error("history");
      render(result.body.results);
      nextCursor = result.body.next_cursor;
      hasMore = result.body.has_more === true && typeof nextCursor === "string";
      loading = false;
      setStatus("");
      updateControls();
    } catch (_error) {
      if (generation === listGen) {
        loading = false;
        setStatus("gallery_error");
        retryBtn.hidden = false; // explicit GET retry only
        moreBtn.hidden = true;
      }
    } finally {
      if (generation === listGen) loading = false;
    }
  }

  let refreshGen = 0;
  async function refreshNewest() {
    const generation = (refreshGen += 1);
    const listAtStart = listGen;
    try {
      const result = await getJson(historyUrl + "?limit=" + PAGE_SIZE);
      if (generation !== refreshGen || listAtStart !== listGen) return;
      if (result.status !== 200 || !validPage(result.body)) return;
      render(result.body.results, {prepend: true});
      if (items.length) setStatus("");
    } catch (_error) { /* The list stays as it was. */ }
  }

  // ---- selection (independent of the active generation) ----------------------------
  async function select(id) {
    if (!cards.has(id)) return;
    selectedId = id;
    for (const [cardId, card] of cards) card.node.setAttribute("aria-pressed", cardId === id ? "true" : "false");
    selectedBox.hidden = false;
    selectedImg.removeAttribute("src");
    setTarget("selected", id);
    const href = await fetchSigned(id);
    if (selectedId !== id) return; // user chose something else meanwhile
    if (href) selectedImg.src = href; else setBarNote("selected", "load_failed");
  }
  selectedImg.addEventListener("error", async () => {
    const id = selectedId;
    if (!id || !selectedImg.getAttribute("src") || selectedImg.dataset.retried === id) return;
    selectedImg.dataset.retried = id;
    const href = await fetchSigned(id, true);
    if (selectedId === id && href) selectedImg.src = href;
  });

  // ---- toolbars ---------------------------------------------------------------------
  const bars = {};
  const shareSupported = typeof navigator.share === "function";
  const copySupported = !!(window.isSecureContext && navigator.clipboard
    && typeof navigator.clipboard.write === "function" && typeof window.ClipboardItem === "function");

  function setupBar(scope) {
    const node = document.querySelector('[data-vq-toolbar="' + scope + '"]');
    if (!node) return;
    const tool = (name) => node.querySelector('[data-vq-tool="' + name + '"]');
    const bar = {
      node, id: null, file: null, busy: false,
      download: tool("download"), share: tool("share"), copy: tool("copy"),
      full: tool("fullscreen"), note: node.querySelector("[data-vq-tool-note]")
    };
    bars[scope] = bar;
    if (bar.share) bar.share.hidden = !shareSupported;
    if (bar.copy) bar.copy.hidden = !copySupported;
    if (bar.share) bar.share.addEventListener("click", () => onShare(scope));
    if (bar.copy) bar.copy.addEventListener("click", () => onCopy(scope));
    if (bar.full) bar.full.addEventListener("click", () => openViewer(scope, bar.full));
  }

  function setBarNote(scope, key) {
    const bar = bars[scope];
    if (bar && bar.note) bar.note.textContent = key ? t(key) : "";
  }

  function setTarget(scope, id) {
    const bar = bars[scope];
    if (!bar) return;
    bar.id = id && uuidPattern.test(id) ? id : null;
    bar.file = null; // at most one prepared file per toolbar
    bar.node.hidden = !bar.id;
    setBarNote(scope, "");
    if (bar.download) {
      if (bar.id) bar.download.href = downloadUrl(bar.id); else bar.download.removeAttribute("href");
    }
  }

  async function onShare(scope) {
    const bar = bars[scope];
    if (!bar || !bar.id || bar.busy) return;
    const id = bar.id;
    bar.busy = true;
    try {
      let file = bar.file && bar.file.id === id ? bar.file.file : null;
      const wasPrepared = file !== null;
      if (!file) {
        setBarNote(scope, "share_preparing");
        const blob = await fetchBlob(id);
        if (bar.id !== id) return; // selection changed while downloading
        file = new File([blob], "VORNEQ-image-" + id + ".png", {type: "image/png"});
        bar.file = {id, file};
      }
      if (typeof navigator.canShare === "function" && !navigator.canShare({files: [file]})) {
        setBarNote(scope, "share_unsupported");
        return;
      }
      try {
        await navigator.share({files: [file], title: "VORNEQ"});
        setBarNote(scope, "");
      } catch (error) {
        const name = error && error.name;
        if (name === "AbortError") { setBarNote(scope, ""); return; } // user cancelled: nothing else happens
        if (name === "NotAllowedError" && !wasPrepared) { setBarNote(scope, "share_retap"); return; }
        setBarNote(scope, "share_failed");
      }
    } catch (_error) {
      if (bar.id === id) setBarNote(scope, "share_failed");
    } finally {
      bar.busy = false;
    }
  }

  async function onCopy(scope) {
    const bar = bars[scope];
    if (!bar || !bar.id || bar.busy) return;
    const id = bar.id;
    bar.busy = true;
    try {
      // A promise inside ClipboardItem keeps the user activation alive while bytes load.
      const item = new window.ClipboardItem({"image/png": fetchBlob(id)});
      await navigator.clipboard.write([item]);
      if (bar.id === id) setBarNote(scope, "copy_done");
    } catch (_error) {
      if (bar.id === id) setBarNote(scope, "copy_failed");
    } finally {
      bar.busy = false;
    }
  }

  // ---- viewer ------------------------------------------------------------------------
  const viewer = document.querySelector("[data-vq-viewer]");
  const vq = (name) => viewer && viewer.querySelector("[data-vq-viewer-" + name + "]");
  let zoom = 1;
  let viewerId = null;
  let opener = null;

  function applyZoom() {
    const img = vq("img");
    img.style.width = String(zoom * 100) + "%";
    vq("zoom-in").disabled = zoom >= ZOOM_MAX;
    vq("zoom-out").disabled = zoom <= ZOOM_MIN;
    vq("zoom-reset").disabled = zoom === ZOOM_MIN;
  }

  function setZoom(value) {
    zoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, value));
    applyZoom();
  }

  async function openViewer(scope, trigger) {
    const bar = bars[scope];
    if (!viewer || typeof viewer.showModal !== "function" || !bar || !bar.id) return;
    const id = bar.id;
    viewerId = id;
    opener = trigger;
    const img = vq("img");
    img.removeAttribute("src");
    img.dataset.retried = "";
    setZoom(1);
    if (!viewer.open) viewer.showModal();
    const href = await fetchSigned(id, true); // fresh GET: no reliance on remembered expiry
    if (viewerId !== id || !viewer.open) return;
    if (href) img.src = href; else vq("status").textContent = t("load_failed");
    vq("close").focus();
  }

  function closeViewer() {
    if (viewer && viewer.open) viewer.close();
  }

  if (viewer) {
    vq("zoom-in").addEventListener("click", () => setZoom(zoom + ZOOM_STEP));
    vq("zoom-out").addEventListener("click", () => setZoom(zoom - ZOOM_STEP));
    vq("zoom-reset").addEventListener("click", () => setZoom(1));
    vq("close").addEventListener("click", closeViewer);
    const native = vq("native");
    if (native) {
      native.hidden = typeof viewer.requestFullscreen !== "function";
      native.addEventListener("click", () => {
        try {
          if (document.fullscreenElement) document.exitFullscreen();
          else viewer.requestFullscreen();
        } catch (_error) { /* Progressive enhancement only. */ }
      });
    }
    vq("img").addEventListener("error", async () => {
      const img = vq("img");
      const id = viewerId;
      if (!id || !img.getAttribute("src") || img.dataset.retried === id) return;
      img.dataset.retried = id;
      const href = await fetchSigned(id, true);
      if (viewerId === id && viewer.open && href) img.src = href;
    });
    viewer.addEventListener("keydown", (event) => {
      if (event.key === "+" || event.key === "=") { event.preventDefault(); setZoom(zoom + ZOOM_STEP); }
      else if (event.key === "-") { event.preventDefault(); setZoom(zoom - ZOOM_STEP); }
      else if (event.key === "0") { event.preventDefault(); setZoom(1); }
    });
    viewer.addEventListener("close", () => {
      viewerId = null;
      const img = vq("img");
      img.removeAttribute("src"); // never keep a signed URL in a hidden element
      vq("status").textContent = "";
      try { if (document.fullscreenElement) document.exitFullscreen(); } catch (_error) {}
      if (opener && typeof opener.focus === "function") opener.focus();
      opener = null;
    });
  }

  // ---- wiring ------------------------------------------------------------------------
  setupBar("current");
  setupBar("selected");
  if (typeof IntersectionObserver === "function") {
    observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        const id = [...cards.keys()].find((key) => cards.get(key).node === entry.target);
        if (!id) continue;
        if (entry.isIntersecting) { visible.add(id); requestThumb(id); } else { visible.delete(id); }
      }
    }, {rootMargin: "200px"});
  }
  moreBtn.addEventListener("click", () => loadPage());
  retryBtn.addEventListener("click", () => loadPage({reset: !items.length}));
  root.addEventListener("vq-image:completed", (event) => {
    const id = event && event.detail ? event.detail.id : null;
    const next = typeof id === "string" && uuidPattern.test(id) ? id : null;
    if (next === currentId) return;
    currentId = next;
    setTarget("current", currentId);
    if (currentId) refreshNewest();
  });
  loadPage({reset: true});
})();
