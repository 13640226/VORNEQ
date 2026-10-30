import assert from 'node:assert/strict';
import { inspectLighthouseReport, runWithIntegrityRetries, sanitizeAttemptDiagnostics } from './lighthouse-integrity.mjs';

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
  const candidate = lhr();
  candidate.audits['largest-contentful-paint'].numericValue = missing;
  const x = inspectLighthouseReport(candidate);
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
  runWithIntegrityRetries({ executeAttempt: async () => ({ lhr: lhr() }), maxAttempts: 4 }),
  RangeError
);
// NO_NAVSTART must remain explicitly invalid, and every attempt must preserve
// bounded, non-sensitive runner and DevTools timing/version evidence.
const rawInstrument = {
  browserVersion: 'HeadlessChrome/140.0.7339.16',
  devtoolsProtocolVersion: '1.3',
  nodeVersion: '22.23.3',
  timingsMs: {
    targetReachabilityMs: 8.327, chromeLaunchMs: 372.99,
    devtoolsReadyMs: 56.45, lighthouseInvocationMs: 6025.57,
    chromeCleanupMs: 41.32, totalAttemptMs: 6512.72
  },
  stages: {
    target: 'complete', chrome: 'complete', devtools: 'complete',
    lighthouse: 'complete', cleanup: 'complete'
  },
  traceNavigation: 'missing-no-navstart',
  runnerBefore: { rssMiB: 116.22, heapUsedMiB: 54.18, freeSystemMiB: 1024.7, loadAverage1m: 0.92 },
  runnerAfter: { rssMiB: 120.5, heapUsedMiB: 56.1, freeSystemMiB: 1004.2, loadAverage1m: 1.01 },
  secret: 'Bearer DO_NOT_LOG',
  url: 'https://private.example/?token=DO_NOT_LOG'
};
const safe = sanitizeAttemptDiagnostics(rawInstrument);
assert.equal(safe.versions.chromium, '140.0.7339.16');
assert.equal(safe.versions.devtoolsProtocol, '1.3');
assert.equal(safe.timingMs.lighthouseInvocationMs, 6025.6);
assert.equal(safe.traceNavigation, 'missing-no-navstart');
assert.equal(safe.stages.cleanup, 'complete');
assert.ok(!JSON.stringify(safe).includes('DO_NOT_LOG'));
assert.ok(!JSON.stringify(safe).includes('private.example'));
const unsanitized = sanitizeAttemptDiagnostics({
  browserVersion: 'Chrome/private.example/?token=secret',
  nodeVersion: '22.0.0; token=secret',
  devtoolsProtocolVersion: '1.3/secret',
  timingsMs: { chromeLaunchMs: -1, lighthouseInvocationMs: Infinity },
  stages: { devtools: 'evil-stage' },
  traceNavigation: 'unknown-with-url'
});
assert.equal(unsanitized.versions.chromium, null);
assert.equal(unsanitized.timingMs.chromeLaunchMs, null);
assert.equal(unsanitized.traceNavigation, 'not-directly-observed');
assert.ok(!JSON.stringify(unsanitized).includes('secret'));

const noNavStart = lhr(null, null, null);
noNavStart.runtimeError = {
  code: 'NO_NAVSTART',
  message: 'Page load failed https://private.example/?token=DO_NOT_LOG NO_NAVSTART'
};
noNavStart.audits['largest-contentful-paint'].scoreDisplayMode = 'error';
const traceRun = await runWithIntegrityRetries({
  executeAttempt: async attempt => ({
    lhr: attempt === 1 ? noNavStart : lhr(),
    attemptDiagnostics: {
      ...rawInstrument, traceNavigation: attempt === 1
        ? 'missing-no-navstart' : 'not-directly-observed'
    }
  }),
  maxAttempts: 2
});
assert.equal(traceRun.status, 'VALID');
assert.equal(traceRun.history[0].diagnostics.runtimeError.code, 'NO_NAVSTART');
assert.equal(traceRun.history[0].diagnostics.runtimeError.message, 'NO_NAVSTART');
assert.equal(traceRun.history[0].instrumentation.traceNavigation, 'missing-no-navstart');
assert.equal(traceRun.history[1].instrumentation.traceNavigation, 'not-directly-observed');
assert.ok(!JSON.stringify(traceRun.history).includes('DO_NOT_LOG'));
assert.ok(!JSON.stringify(traceRun.history).includes('private.example'));
const stillInvalidTrace = await runWithIntegrityRetries({
  executeAttempt: async () => ({ lhr: noNavStart, attemptDiagnostics: rawInstrument }),
  maxAttempts: 2
});
assert.equal(stillInvalidTrace.status, 'MEASUREMENT_INVALID');
assert.equal(stillInvalidTrace.attempts, 2);
assert.equal(stillInvalidTrace.history[1].instrumentation.stages.cleanup, 'complete');

// A third attempt is permitted only when the second report is NO_NAVSTART.
let noNavTries = 0;
const rescuedThird = await runWithIntegrityRetries({
  executeAttempt: async () => {
    noNavTries += 1;
    return { lhr: noNavTries < 3 ? noNavStart : lhr() };
  },
  maxAttempts: 3
});
assert.equal(rescuedThird.status, 'VALID');
assert.equal(rescuedThird.attempts, 3);
let ordinaryInvalidTries = 0;
const boundedOrdinary = await runWithIntegrityRetries({
  executeAttempt: async () => {
    ordinaryInvalidTries += 1;
    return { lhr: lhr(null, null, null) };
  },
  maxAttempts: 3
});
assert.equal(boundedOrdinary.status, 'MEASUREMENT_INVALID');
assert.equal(ordinaryInvalidTries, 2);
let persistentNavTries = 0;
const persistentNav = await runWithIntegrityRetries({
  executeAttempt: async () => {
    persistentNavTries += 1;
    return { lhr: noNavStart };
  },
  maxAttempts: 3
});
assert.equal(persistentNav.status, 'MEASUREMENT_INVALID');
assert.equal(persistentNavTries, 3);

// Timing diagnostics contract: a valid report, absent timing, and NO_NAVSTART.
// These are synthetic fixtures; the raw Lighthouse 12.8.2 timing payload
// was not retained in the historical CI artifact.
const timedValid = lhr();
timedValid.timing = {
  total: 4200.12,
  entries: [
    { name: 'lh:runner:gather', duration: 120.4 },
    { name: 'safe_phase', duration: 35.55 },
    { name: 'unsafe/phase', duration: 10 },
    { name: 'https:secret', duration: 12 },
    { name: 'invalid_duration', duration: -1 }
  ]
};
const timedResult = inspectLighthouseReport(timedValid);
assert.equal(timedResult.status, 'VALID');
assert.equal(timedResult.diagnostics.trace.lighthouseReportedTotalMs, 4200.1);
assert.deepEqual(timedResult.diagnostics.trace.phases, [
  { name: 'lh:runner:gather', durationMs: 120.4 },
  { name: 'safe_phase', durationMs: 35.6 },
  { name: 'invalid_duration', durationMs: null }
]);
const withoutTiming = inspectLighthouseReport(lhr());
assert.equal(withoutTiming.status, 'VALID');
assert.equal(withoutTiming.diagnostics.trace.lighthouseReportedTotalMs, null);
assert.deepEqual(withoutTiming.diagnostics.trace.phases, []);
const noNavWithTiming = lhr(null, null, null);
noNavWithTiming.runtimeError = { code: 'NO_NAVSTART', message: 'NO_NAVSTART' };
noNavWithTiming.timing = { total: 3100, entries: [{ name: 'safe_phase', duration: 900 }] };
const noNavResult = inspectLighthouseReport(noNavWithTiming);
assert.equal(noNavResult.status, 'MEASUREMENT_INVALID');
assert.equal(noNavResult.diagnostics.trace.navigationStart, 'missing-no-navstart');
assert.deepEqual(noNavResult.diagnostics.trace.phases, [{ name: 'safe_phase', durationMs: 900 }]);

console.log('Lighthouse measurement integrity and retry self-tests passed.');
