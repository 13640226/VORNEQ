import assert from 'node:assert/strict';
import { LOCALES, PERF_THRESHOLDS, PROFILES, SURFACES } from './contract.mjs';

assert.deepEqual(LOCALES, ['fa', 'en', 'de']);
assert.equal(SURFACES.length, 10);
assert.deepEqual(SURFACES.map(s => s.id), ['V-01','V-02','V-03','V-04','V-05','V-06','V-07','V-08','V-09','V-10']);
assert.ok(SURFACES.filter(s => s.perf === 'full').length >= 4);
assert.equal(PERF_THRESHOLDS.lcpMs, 2500);
assert.equal(PERF_THRESHOLDS.cls, 0.10);
assert.equal(PERF_THRESHOLDS.inp.targetMs, 200);
assert.match(PERF_THRESHOLDS.inp.classification, /blocked\/unknown/);
assert.deepEqual(Object.keys(PROFILES).sort(), ['desktop', 'mobile']);
for (const surface of SURFACES) {
  assert.ok(surface.path.startsWith('/'));
  assert.ok(['full', 'smoke'].includes(surface.a11y));
  assert.ok(['full', 'sample'].includes(surface.perf));
}
console.log('Quality verification contract self-test passed.');
