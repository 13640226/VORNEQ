// Read-only, best-effort Lighthouse 12.8.2 trace inspection. No raw trace persistence.
const MAX_EVENTS = 250000;
const TIME_BUDGET_MS = 250;
const HEAP_BUDGET_BYTES = 32 * 1048576;
const CHECK_INTERVAL = 256;
const SOURCE = 'lighthouse-12.8.2-runner-artifacts';
const unknown = (count = 0, access = 'unavailable', key = null) => ({
  source: SOURCE, traceAccess: access, traceKey: key, navigationStart: 'unknown',
  matchingEventCount: null, scannedEventCount: count, scanComplete: false
});
export function inspectExistingNavigationTrace(artifacts, readers = {}) {
  const now = readers.now ?? (() => performance.now());
  const heapUsed = readers.heapUsed ?? (() => process.memoryUsage().heapUsed);
  let scanned = 0, access = 'unavailable', key = null;
  try {
    const started = now();
    const heapStart = heapUsed();
    if (!Number.isFinite(started) || !Number.isFinite(heapStart)) return unknown();
    const candidates = [
      ['Trace', () => artifacts?.Trace],
      ['TraceError', () => artifacts?.TraceError],
      ['traces.defaultPass', () => artifacts?.traces?.defaultPass],
      ['traces.pageLoadError-defaultPass', () => artifacts?.traces?.['pageLoadError-defaultPass']]
    ];
    let events;
    for (const [name, get] of candidates) {
      const trace = get();
      if (Array.isArray(trace?.traceEvents)) { key = name; events = trace.traceEvents; break; }
    }
    if (!events) return unknown();
    access = 'available';
    const length = events.length;
    const limit = Math.min(length, MAX_EVENTS);
    let matches = 0;
    const withinBudget = () => {
      const ms = now() - started;
      const bytes = heapUsed() - heapStart;
      return Number.isFinite(ms) && ms >= 0 && ms <= TIME_BUDGET_MS &&
        Number.isFinite(bytes) && bytes <= HEAP_BUDGET_BYTES;
    };
    if (!withinBudget()) return unknown(scanned, access, key);
    for (let i = 0; i < limit; i++) {
      if ((i % CHECK_INTERVAL) === 0 && !withinBudget()) return unknown(scanned, access, key);
      if (events[i]?.name === 'navigationStart') matches++;
      scanned++;
    }
    if (!withinBudget()) return unknown(scanned, access, key);
    const complete = length <= MAX_EVENTS;
    return {
      source: SOURCE, traceAccess: access, traceKey: key,
      navigationStart: matches ? 'event-name-observed' :
        (complete ? 'event-name-not-observed-in-available-trace' : 'unknown'),
      matchingEventCount: matches, scannedEventCount: scanned, scanComplete: complete
    };
  } catch {
    return unknown(scanned, access, key);
  }
}
