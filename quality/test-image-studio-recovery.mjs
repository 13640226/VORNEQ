import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import vm from "node:vm";

const source = readFileSync(new URL("../assets/js/image-studio.js", import.meta.url), "utf8");
const base = "/api/ai/v1/images/jobs/";
const uuid = "8b5fbe11-8e1d-4de4-82b8-fac4f010c464";
const another = "71c1d0c6-4b4c-41ad-90f7-510b8ecd1f81";
const job = (status, id = uuid) => ({id, status});
const reply = (status, body, retry) => ({
  status, json: async () => body,
  headers: {get: (name) => name === "Retry-After" && retry !== undefined ? String(retry) : null}
});
const flush = () => new Promise(resolve => setImmediate(resolve));

function page({owner = "3", storage = new Map(), responses = []} = {}) {
  const handlers = new Map();
  const element = (name) => ({
    dataset: {}, hidden: false, disabled: false, value: "", checked: false, textContent: "",
    addEventListener(event, fn) {handlers.set(name + ":" + event, fn);},
    removeAttribute(key) {delete this[key];},
    checkValidity() {return true;}, reportValidity() {}
  });
  const elements = Object.fromEntries(
    ["form", "prompt", "size", "consent", "submit", "check", "status", "figure",
      "preview", "open", "ack", "ack-label", "new"].map(n => [n, element(n)]));
  elements.brand = element("brand");
  elements.brand.dataset.state = "idle";
  elements.form.querySelector = () => ({value: "synthetic-csrf"});
  elements.prompt.value = "synthetic landscape";
  elements.size.value = "1024x1024";
  elements.consent.checked = true;
  elements.status.dataset = Object.fromEntries(
    ["wait", "sending", "queued", "running", "completed", "failed", "uncertain", "error",
     "invalid", "rejected", "rateLimited", "dailyLimit", "queueFull", "misconfigured", "pollStopped",
     "recoveryError", "acknowledged", "unknownMissing"].map(k => [k, k === "rateLimited" ? "rate {seconds}" : k]));
  const root = {
    dataset: {createUrl: base, userId: owner},
    querySelector(selector) {
      if (selector === "[data-vq-ai-brand]") return elements.brand;
      const match = /^\[data-vq-image-(.*)\]$/.exec(selector);
      assert.ok(match, selector);
      return elements[match[1]];
    }
  };
  const document = {hidden: false, querySelector: () => root,
    addEventListener: (event, fn) => handlers.set("document:" + event, fn)};
  const window = {
    crypto: {randomUUID: () => uuid},
    localStorage: {
      getItem: key => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: key => storage.delete(key)
    },
    addEventListener: (event, fn) => handlers.set("window:" + event, fn)
  };
  let timerId = 0;
  const timers = new Map();
  const calls = [];
  const navigator = {onLine: true};
  const fetch = async (url, options) => {
    calls.push({url, ...options});
    assert.ok(responses.length, "unexpected " + options.method + " " + url);
    const result = responses.shift();
    if (result instanceof Error) throw result;
    return typeof result === "function" ? result() : result;
  };
  const context = vm.createContext({window, document, navigator, URL, AbortController, fetch,
    setTimeout(fn, delay) {timers.set(++timerId, {fn, delay}); return timerId;},
    clearTimeout(id) {timers.delete(id);}});
  vm.runInContext(source, context, {filename: "image-studio.js"});
  const fire = (name, event) => handlers.get(name + ":" + event)?.({preventDefault() {}});
  async function tick() {
    const entries = [...timers.entries()].filter(([, t]) => t.delay < 15000);
    assert.equal(entries.length, 1, "exactly one poll timer");
    const [id, timer] = entries[0];
    timers.delete(id); timer.fn(); await flush();
  }
  return {elements, calls, timers, storage, document, navigator, fire, tick};
}
const empty = () => [reply(200, {results: []}), reply(200, {id: null})];
const getOnly = p => assert.ok(p.calls.every(c => c.method === "GET"));

test("server recovery and completion perform GETs only", async () => {
  const p = page({responses: [reply(200, {results: [job("queued")]}), reply(200, job("running")),
    reply(200, {...job("completed"), image_url: "https://private.example.test/signed"})]});
  await flush(); assert.equal(p.elements.status.textContent, "running");
  assert.equal(p.elements.brand.dataset.state, "thinking");
  await p.tick(); assert.equal(p.elements.figure.hidden, false);
  assert.equal(p.elements.brand.dataset.state, "idle");
  assert.equal(p.elements.preview.src, "https://private.example.test/signed");
  assert.equal(p.timers.size, 0); getOnly(p);
});

test("owner-scoped pending UUID survives reload and uncertain acknowledgment", async () => {
  const storage = new Map();
  const p = page({storage, responses: [...empty(), new Error("lost response"), reply(200, job("uncertain"))]});
  await flush();
  await p.fire("form", "submit"); await flush();
  assert.equal(p.calls.filter(c => c.method === "POST").length, 1);
  assert.ok(storage.get("vq.image.recovery.3").includes(uuid));
  assert.ok(!storage.get("vq.image.recovery.3").includes("synthetic landscape"));
  await p.tick(); assert.equal(p.elements.status.textContent, "uncertain");
  assert.equal(p.elements.brand.dataset.state, "error");
  p.elements.ack.checked = true; p.fire("ack", "change");
  assert.equal(JSON.parse(storage.get("vq.image.recovery.3")).acknowledged, true);
  assert.equal(p.elements.submit.disabled, true);
  const reload = page({storage, responses: [reply(200, job("uncertain"))]});
  await flush(); getOnly(reload); assert.equal(reload.elements.ack.checked, true);
  const other = page({owner: "4", storage, responses: empty()});
  await flush(); getOnly(other);
  assert.ok(other.calls.every(c => !c.url.includes(uuid)));
});

test("429 is definitive, no polling or new POST until explicit new request", async () => {
  const p = page({responses: [...empty(), reply(429, {error: "rate_limited", error_code: "rate_limited",
    request_rejected: true, retry_after_seconds: 41}, 41), reply(200, {results: []})]});
  await flush();
  await p.fire("form", "submit"); await flush();
  assert.equal(p.elements.status.textContent, "rate 41");
  assert.equal(p.elements.check.hidden, true);
  assert.equal(p.timers.size, 0);
  await p.fire("form", "submit");
  assert.equal(p.calls.filter(c => c.method === "POST").length, 1);
  await p.fire("new", "click"); await flush();
  assert.equal(p.elements.consent.checked, false);
  assert.equal(p.elements.submit.disabled, false);
  assert.equal(p.calls.filter(c => c.method === "POST").length, 1);
});

test("GET polling pauses while hidden/offline, resumes once, remains bounded", async () => {
  const p = page({responses: [reply(200, {results: [job("queued")]}),
    ...Array.from({length: 21}, () => reply(200, job("running")))]});
  await flush();
  p.document.hidden = true; p.fire("document", "visibilitychange");
  assert.equal(p.timers.size, 0);
  p.document.hidden = false; p.fire("document", "visibilitychange");
  p.fire("window", "online");
  assert.equal(p.timers.size, 1);
  p.navigator.onLine = false; p.fire("window", "offline"); assert.equal(p.timers.size, 0);
  p.navigator.onLine = true; p.fire("window", "online");
  for (let i = 0; i < 20; i++) await p.tick();
  assert.equal(p.timers.size, 0);
  assert.match(p.elements.status.textContent, /pollStopped/);
  getOnly(p);
});

test("a reload after job completed discovers latest identity and refreshes signed URL", async () => {
  const p = page({responses: [reply(200, {results: []}), reply(200, {id: uuid}),
    reply(200, {...job("completed"), image_url: "https://private.example.test/new"})]});
  await flush(); getOnly(p);
  assert.equal(p.elements.preview.src, "https://private.example.test/new");
  assert.ok(!p.storage.get("vq.image.recovery.3").includes("https:"));
});

test("unverified response and missing job cannot unlock a duplicate POST", async () => {
  const p = page({responses: [...empty(), reply(500, {error: "unavailable"}), reply(404, {})]});
  await flush(); await p.fire("form", "submit"); await flush();
  await p.tick();
  assert.equal(p.elements.submit.disabled, true);
  assert.equal(p.elements.new.hidden, true);
  assert.equal(p.elements.status.textContent, "unknownMissing");
  assert.equal(p.calls.filter(c => c.method === "POST").length, 1);
  assert.ok(p.storage.get("vq.image.recovery.3").includes(uuid));
});

test("invalid detail identity never displays a different job", async () => {
  const p = page({responses: [reply(200, {results: [job("queued")]}),
    reply(200, {...job("completed", another), image_url: "https://wrong.example.test"})]});
  await flush(); getOnly(p);
  assert.equal(p.elements.preview.src, undefined);
  assert.equal(p.elements.status.textContent, "invalid");
  assert.equal(p.elements.submit.disabled, true);
});

test("queue refusal is definitive and never auto retries", async () => {
  const p = page({responses: [...empty(), reply(429, {error: "active_queue_full",
    error_code: "active_queue_full", request_rejected: true, retry_after_seconds: 30}, 30)]});
  await flush(); await p.fire("form", "submit"); await flush();
  assert.equal(p.elements.status.textContent, "queueFull");
  assert.equal(p.calls.filter(c => c.method === "POST").length, 1);
  assert.equal(p.storage.has("vq.image.recovery.3"), false);
});
