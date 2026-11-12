import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import vm from 'node:vm';

const here = dirname(fileURLToPath(import.meta.url));
const localSource = resolve(here, '../assets/js/homepage-ai-workspace-v1.js');
// The isolated quality runner copies /src/quality to /tmp/quality; app source
// stays mounted read-only at /src, never executing code on the host runner.
const script = readFileSync(
  existsSync(localSource) ? localSource : '/src/assets/js/homepage-ai-workspace-v1.js',
  'utf8'
);

function event(key, extra = {}) {
  return { key, ...extra, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
}
function emitter() {
  const handlers = new Map();
  return {
    addEventListener(type, callback) {
      (handlers.get(type) || handlers.set(type, []).get(type)).push(callback);
    },
    emit(type, e = event(type)) {
      for (const callback of handlers.get(type) || []) callback(e);
      return e;
    }
  };
}
function setup({ readyState = 'complete', withRoot = true, requestSubmit = true } = {}) {
  const input = Object.assign(emitter(), {
    value: '', maxLength: 200, focused: false, selection: null,
    focus() { this.focused = true; },
    setSelectionRange(a, b) { this.selection = [a, b]; }
  });
  const count = { textContent: '' };
  const send = { disabled: false, clicks: 0, click() { this.clicks += 1; form.emit('submit'); } };
  const form = Object.assign(emitter(), {
    querySelector(selector) { assert.equal(selector, 'button[type="submit"]'); return send; },
    submissions: 0,
    ...(requestSubmit ? { requestSubmit() { this.submissions += 1; this.emit('submit'); } } : {})
  });
  const example = Object.assign(emitter(), {
    getAttribute(name) { return name === 'data-vq-prompt' ? 'اسناد و مدارک' : null; }
  });
  const root = {
    querySelector(selector) {
      return ({
        '[data-vq-composer]': form,
        '[data-vq-composer-input]': input,
        '[data-vq-composer-count]': count
      })[selector];
    },
    querySelectorAll(selector) { assert.equal(selector, '[data-vq-example]'); return [example]; }
  };
  const document = Object.assign(emitter(), {
    readyState,
    querySelector(selector) {
      assert.equal(selector, '[data-vq-ai-workspace]');
      return withRoot ? root : null;
    }
  });
  vm.runInNewContext(script, { document });
  return { input, count, send, form, example, document };
}

{
  const x = setup();
  assert.equal(x.count.textContent, '0/200');
  assert.equal(x.send.disabled, true);
  x.input.value = '   ';
  x.input.emit('input');
  assert.equal(x.send.disabled, true);
  assert.equal(x.count.textContent, '3/200');
  assert.equal(x.form.emit('submit').defaultPrevented, true);
  assert.equal(x.input.focused, true);
  x.input.value = '  search text  ';
  x.input.emit('input');
  assert.equal(x.send.disabled, false);
  assert.equal(x.form.emit('submit').defaultPrevented, false);
  assert.equal(x.input.value, 'search text');
  assert.equal(x.count.textContent, '11/200');
}
{
  const x = setup();
  x.example.emit('click');
  assert.equal(x.input.value, 'اسناد و مدارک');
  assert.equal(x.send.disabled, false);
  assert.equal(x.input.focused, true);
  assert.equal(x.input.selection[0], x.input.value.length);
}
{
  const x = setup();
  x.input.value = 'قرارداد';
  x.input.emit('input');
  assert.equal(x.input.emit('keydown', event('Enter', { ctrlKey: true, isComposing: true })).defaultPrevented, false);
  assert.equal(x.input.emit('keydown', event('Enter', { ctrlKey: true, keyCode: 229 })).defaultPrevented, false);
  assert.equal(x.form.submissions, 0);
  assert.equal(x.input.emit('keydown', event('Enter', { ctrlKey: true })).defaultPrevented, true);
  assert.equal(x.input.emit('keydown', event('Enter', { metaKey: true })).defaultPrevented, true);
  assert.equal(x.form.submissions, 2);
  assert.equal(x.input.emit('keydown', event('Enter')).defaultPrevented, false);
}
{
  const x = setup({ requestSubmit: false });
  x.input.value = 'query';
  x.input.emit('input');
  x.input.emit('keydown', event('Enter', { ctrlKey: true }));
  assert.equal(x.send.clicks, 1);
}
{
  const x = setup({ readyState: 'loading' });
  assert.equal(x.count.textContent, '');
  x.document.emit('DOMContentLoaded');
  assert.equal(x.count.textContent, '0/200');
  setup({ withRoot: false });
}
{
  const x = setup();
  x.input.value = 'x'.repeat(205);
  x.form.emit('submit');
  assert.equal(x.input.value.length, 200);
  assert.equal(x.count.textContent, '200/200');
}
console.log('Homepage AI workspace interaction tests passed (6 scenarios).');
