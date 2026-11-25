// V7-03: SSE stream parser – frame and UTF-8 boundary splits, replay, invalid input.
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import vm from 'node:vm';

const here = dirname(fileURLToPath(import.meta.url));
const local = resolve(here, '../assets/js/vq-stream-parser.js');
const source = readFileSync(existsSync(local) ? local : '/src/assets/js/vq-stream-parser.js', 'utf8');
const sandbox = { TextDecoder, globalThis: {} };
sandbox.window = sandbox;
vm.runInNewContext(source, sandbox);
const { create } = sandbox.VQStreamParser;

function frame(seq, type, payload) {
  const body = { type, sequence_number: seq, request_id: null, conversation_id: 'c', response_id: 'r',
    timestamp: 't', payload };
  return `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify(body)}\n\n`;
}
const texts = ['هوش مصنوعی‌ها ', 'Größe äöü ß ', 'emoji 😀🚀 ', 'English.'];
const stream = frame(1, 'response.created', { protocol: 1 }) +
  texts.map((t, i) => frame(i + 2, 'response.delta', { text: t })).join('') +
  frame(texts.length + 2, 'response.completed', { response: { answer: texts.join('') } });
const bytes = new TextEncoder().encode(stream);

function collect(chunks) {
  const parser = create();
  const events = [];
  for (const chunk of chunks) events.push(...parser.feed(chunk));
  events.push(...parser.end());
  return events;
}

// 1) whole stream
const whole = collect([bytes]);
assert.equal(whole.length, texts.length + 2);
assert.equal(whole.filter((e) => e.type === 'response.delta').map((e) => e.payload.text).join(''), texts.join(''));

// 2) every possible single split point (frames AND multibyte UTF-8 sequences cut)
for (let cut = 1; cut < bytes.length; cut += 1) {
  const events = collect([bytes.slice(0, cut), bytes.slice(cut)]);
  assert.deepEqual(events.map((e) => e.sequence_number), whole.map((e) => e.sequence_number), `cut ${cut}`);
  assert.equal(events.filter((e) => e.type === 'response.delta').map((e) => e.payload.text).join(''),
    texts.join(''), `text at cut ${cut}`);
}

// 3) byte-by-byte delivery
const single = collect(Array.from(bytes, (b) => Uint8Array.of(b)));
assert.equal(single.length, whole.length);

// 4) replayed / out-of-order events are dropped; invalid JSON and unknown types ignored
const noisy = frame(1, 'response.created', {}) + frame(2, 'response.delta', { text: 'a' }) +
  frame(2, 'response.delta', { text: 'DUP' }) + frame(1, 'response.delta', { text: 'OLD' }) +
  'data: {not json}\n\n' + frame(3, 'response.unknown', {}) + frame(4, 'response.delta', { text: 'b' });
const filtered = collect([new TextEncoder().encode(noisy)]);
assert.deepEqual(filtered.map((e) => e.payload.text ?? e.type), ['response.created', 'a', 'b']);

// 5) oversized buffer is refused (backpressure / abuse guard)
assert.throws(() => create().feed(new TextEncoder().encode('x'.repeat(262145))), /oversized/);

console.log(`Chat stream parser tests passed (${bytes.length} split points).`);
