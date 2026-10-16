import assert from 'node:assert/strict';
import { inspectLighthouseReport, runWithIntegrityRetries } from './lighthouse-integrity.mjs';

function lhr(lcp = 1100, cls = 0.01, score = 0.98) {
  return {
    audits: {
      'largest-contentful-paint': { numericValue: lcp, scoreDisplayMode: 'numeric' },
      'cumulative-layout-shift': { numericValue: cls, scoreDisplayMode: 'numeric' }
    },
    categories: { performance: { score } }
  };
}
const valid = inspectLighthouseReport(lhr());
assert.equal(valid.status, 'VALID');
assert.deepEqual(valid.observed, { lcpMs: 1100, cls: 0.01, performanceScore: 0.98 });
for (const missing of [null, NaN, Infinity, -Infinity, undefined]) {
  const x = inspectLighthouseReport(lhr(missing, 0.01, 0.98));
  assert.equal(x.status, 'MEASUREMENT_INVALID');
  assert.equal(x.observed.lcpMs, null);
  assert.ok(x.diagnostics.reasons.includes('missing-or-nonfinite-metrics'));
}
assert.equal(inspectLighthouseReport(lhr(500, -1, 0.98)).status, 'MEASUREMENT_INVALID');
assert.equal(inspectLighthouseReport(lhr(500, 0, 1.2)).status, 'MEASUREMENT_INVALID');
const withError = lhr();
withError.runtimeError = { code: 'ERRORED_DOCUMENT_REQUEST', message: 'Page failed' };
assert.equal(inspectLighthouseReport(withError).status, 'MEASUREMENT_INVALID');
assert.equal(inspectLighthouseReport(withError).diagnostics.runtimeError.code, 'ERRORED_DOCUMENT_REQUEST');
const auditError = lhr();
auditError.audits['largest-contentful-paint'].scoreDisplayMode = 'error';
assert.equal(inspectLighthouseReport(auditError).status, 'MEASUREMENT_INVALID');

const retryEvents = [];
let active = 0;
let maxActive = 0;
const rescued = await runWithIntegrityRetries({
  executeAttempt: async (attempt) => {
    active += 1; maxActive = Math.max(maxActive, active);
    await Promise.resolve();
    active -= 1;
    return { url: 'http://localhost/en/', lhr: attempt === 1 ? lhr(null, null, null) : lhr() };
  },
  onRetry: async event => { assert.equal(active, 0); retryEvents.push(event); }
});
assert.equal(rescued.status, 'VALID');
assert.equal(rescued.attempts, 2);
assert.deepEqual(rescued.history.map(x => x.status), ['MEASUREMENT_INVALID', 'VALID']);
assert.equal(retryEvents.length, 1);
assert.equal(retryEvents[0].kind, 'incomplete-report');
assert.equal(maxActive, 1);
const exhausted = await runWithIntegrityRetries({
  executeAttempt: async () => ({ lhr: lhr(null, NaN, null) }),
  onRetry: async () => {}
});
assert.equal(exhausted.status, 'MEASUREMENT_INVALID');
assert.equal(exhausted.attempts, 2);
assert.equal(exhausted.history.length, 2);
assert.equal(exhausted.observed.lcpMs, null);

let tries = 0;
const afterTransientError = await runWithIntegrityRetries({
  executeAttempt: async () => {
    tries += 1;
    if (tries === 1) throw new Error('Target closed');
    return { lhr: lhr() };
  },
  isRecoverableError: e => e.message === 'Target closed'
});
assert.equal(afterTransientError.status, 'VALID');
assert.equal(tries, 2);
await assert.rejects(
  runWithIntegrityRetries({
    executeAttempt: async () => { throw new Error('Chrome cleanup failed'); },
    isRecoverableError: () => false
  }),
  /Chrome cleanup failed/
);
await assert.rejects(
  runWithIntegrityRetries({ executeAttempt: async () => ({ lhr: lhr() }), maxAttempts: 3 }),
  RangeError
);
console.log('Lighthouse measurement integrity and retry self-tests passed.');
