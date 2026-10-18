// Pure Lighthouse measurement validation and safe, bounded retry orchestration.
// Product threshold decisions are deliberately separate from measurement integrity.
const METRICS = [
  ['lcpMs', 'largest-contentful-paint'],
  ['cls', 'cumulative-layout-shift'],
  ['performanceScore', null]
];

// Only named diagnostic classes are surfaced: never copy arbitrary page content,
// request URLs, authorization headers, cookie values, or hostnames to CI artifacts.
function clipped(value) {
  if (value == null) return null;
  const text = String(value);
  if (text.includes('NO_NAVSTART')) return 'NO_NAVSTART';
  if (text.includes('Target closed')) return 'TARGET_CLOSED';
  if (text.includes('Protocol error')) return 'PROTOCOL_ERROR';
  if (/timeout|timed out/i.test(text)) return 'TIMEOUT';
  if (/cleanup/i.test(text)) return 'CLEANUP_FAILURE';
  return 'MESSAGE_REDACTED';
}

function safeCode(value) {
  const candidate = String(value ?? '');
  return /^[A-Z][A-Z0-9_]{0,63}$/.test(candidate) ? candidate : 'UNCLASSIFIED';
}

function safeNumber(value, max) {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= max
    ? Math.round(value * 10) / 10 : null;
}

function sanitizeV5Trace(data) {
  const allowedKeys = ['Trace', 'TraceError', 'traces.defaultPass', 'traces.pageLoadError-defaultPass'];
  const allowedStates = ['event-name-observed', 'event-name-not-observed-in-available-trace', 'unknown'];
  const boundedCount = n => Number.isInteger(n) && n >= 0 && n <= 250000 ? n : null;
  return {
    source: 'lighthouse-12.8.2-runner-artifacts',
    traceAccess: data?.traceAccess === 'available' ? 'available' : 'unavailable',
    traceKey: allowedKeys.includes(data?.traceKey) ? data.traceKey : null,
    navigationStart: allowedStates.includes(data?.navigationStart) ? data.navigationStart : 'unknown',
    matchingEventCount: boundedCount(data?.matchingEventCount),
    scannedEventCount: boundedCount(data?.scannedEventCount),
    scanComplete: data?.scanComplete === true,
    scanElapsedMs: safeNumber(data?.scanElapsedMs, 180000),
    heapDeltaMiB: typeof data?.heapDeltaMiB === 'number' && Number.isFinite(data.heapDeltaMiB) && Math.abs(data.heapDeltaMiB) <= 100000 ? Math.round(data.heapDeltaMiB * 100) / 100 : null
  };
}
export function sanitizeAttemptDiagnostics(data) {
  if (!data || typeof data !== 'object') return null;
  const timings = {};
  for (const key of [
    'targetReachabilityMs', 'chromeLaunchMs', 'devtoolsReadyMs',
    'lighthouseInvocationMs', 'chromeCleanupMs', 'totalAttemptMs'
  ]) timings[key] = safeNumber(data.timingsMs?.[key], 180000);
  const states = {};
  for (const key of ['target', 'chrome', 'devtools', 'lighthouse', 'cleanup']) {
    const value = data.stages?.[key];
    states[key] = ['pending', 'complete', 'failed', 'not-started'].includes(value)
      ? value : 'not-started';
  }
  const versionMatch = String(data.browserVersion ?? '')
    .match(/^(?:HeadlessChrome|Chrome|Chromium)\/(\d+(?:\.\d+){3})$/);
  const protocol = String(data.devtoolsProtocolVersion ?? '');
  const node = String(data.nodeVersion ?? '');
  const trace = data.traceNavigation === 'missing-no-navstart'
    ? 'missing-no-navstart' : 'not-directly-observed';
  const sanitizeRunner = snapshot => ({
    rssMiB: safeNumber(snapshot?.rssMiB, 100000),
    heapUsedMiB: safeNumber(snapshot?.heapUsedMiB, 100000),
    freeSystemMiB: safeNumber(snapshot?.freeSystemMiB, 1000000),
    loadAverage1m: safeNumber(snapshot?.loadAverage1m, 10000)
  });
  return {
    timingMs: timings,
    stages: states,
    versions: {
      chromium: versionMatch?.[1] ?? null,
      node: /^\d+\.\d+\.\d+$/.test(node) ? node : null,
      devtoolsProtocol: /^\d+(?:\.\d+){1,2}$/.test(protocol) ? protocol : null
    },
    traceNavigation: trace,
    v5Trace: sanitizeV5Trace(data.v5Trace),
    resources: {
      before: sanitizeRunner(data.runnerBefore),
      after: sanitizeRunner(data.runnerAfter)
    }
  };
}

/**
 * Diagnostic-only, allowlisted LHR shape indicators. No URL, trace payload,
 * network request content, or unbounded error text is retained.
 * These are NOT direct observations of a navigationStart trace event.
 */
export function inspectLighthouseNavigationEvidence(lhr) {
  const entries = lhr?.timing?.entries;
  const requests = lhr?.audits?.['network-requests']?.details?.items;
  const nav = lhr?.audits?.['navigation-timing'];
  const safeCount = value => Array.isArray(value)
    ? Math.min(value.length, 100000) : null;
  return {
    fetchTimePresent: typeof lhr?.fetchTime === 'string',
    timingEntryCount: safeCount(entries),
    networkRequestAuditItemCount: safeCount(requests),
    navigationTimingAuditPresent: nav != null,
    navigationTimingNumericMs: safeNumber(nav?.numericValue, 180000),
    directTraceNavigationStartObserved: false,
    evidenceScope: 'lhr-metadata-only'
  };
}

function auditDetails(audit) {
  return {
    numericValue: typeof audit?.numericValue === 'number' && Number.isFinite(audit.numericValue)
      ? audit.numericValue : null,
    scoreDisplayMode: audit?.scoreDisplayMode ?? null,
    errorMessage: clipped(audit?.errorMessage)
  };
}

export function inspectLighthouseReport(lhr) {
  const lcp = lhr?.audits?.['largest-contentful-paint'];
  const cls = lhr?.audits?.['cumulative-layout-shift'];
  const score = lhr?.categories?.performance?.score;
  const observed = {
    lcpMs: typeof lcp?.numericValue === 'number' && Number.isFinite(lcp.numericValue)
      ? lcp.numericValue : null,
    cls: typeof cls?.numericValue === 'number' && Number.isFinite(cls.numericValue)
      ? cls.numericValue : null,
    performanceScore: typeof score === 'number' && Number.isFinite(score) ? score : null
  };
  const reasons = [];
  if (lhr?.runtimeError) reasons.push('runtime-error');
  if (METRICS.some(([key]) => observed[key] === null)) reasons.push('missing-or-nonfinite-metrics');
  if (observed.lcpMs !== null && observed.lcpMs < 0 ||
      observed.cls !== null && observed.cls < 0 ||
      observed.performanceScore !== null &&
        (observed.performanceScore < 0 || observed.performanceScore > 1)) {
    reasons.push('out-of-range-metrics');
  }
  if (lcp?.scoreDisplayMode === 'error' || cls?.scoreDisplayMode === 'error') {
    reasons.push('audit-error');
  }
  return {
    status: reasons.length === 0 ? 'VALID' : 'MEASUREMENT_INVALID',
    observed,
    diagnostics: {
      reasons,
      runtimeError: lhr?.runtimeError
        ? { code: safeCode(lhr.runtimeError.code), message: clipped(lhr.runtimeError.message) }
        : null,
      runtimeWarnings: (Array.isArray(lhr?.runWarnings) ? lhr.runWarnings : []).slice(0, 10).map(clipped),
      audits: {
        'largest-contentful-paint': auditDetails(lcp),
        'cumulative-layout-shift': auditDetails(cls)
      },
      trace: {
        navigationStart: safeCode(lhr?.runtimeError?.code) === 'NO_NAVSTART'
          ? 'missing-no-navstart' : 'not-directly-observed',
        lighthouseReportedTotalMs: safeNumber(lhr?.timing?.total, 180000)
      },
      navigationEvidence: inspectLighthouseNavigationEvidence(lhr),
      performanceCategoryScore: observed.performanceScore
    }
  };
}

function errorDetails(error) {
  return {
    name: /^[A-Za-z][A-Za-z0-9]{0,63}$/.test(String(error?.name ?? ''))
      ? String(error.name) : 'Error',
    message: clipped(error?.message ?? error),
    attemptDiagnostics: sanitizeAttemptDiagnostics(error?.attemptDiagnostics)
  };
}

// executeAttempt MUST await browser shutdown/cleanup before resolving or rejecting.
// Sequential awaits guarantee no overlapping attempts. The caller owns Chrome cleanup.
export async function runWithIntegrityRetries({
  executeAttempt,
  isRecoverableError = () => false,
  onRetry = async () => {},
  maxAttempts = 2
}) {
  if (!Number.isInteger(maxAttempts) || maxAttempts < 1 || maxAttempts > 2) {
    throw new RangeError('Lighthouse attempts must be 1 or 2');
  }
  const history = [];
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    let completed;
    try {
      completed = await executeAttempt(attempt);
    } catch (error) {
      const recoverable = isRecoverableError(error);
      history.push({ attempt, status: 'ATTEMPT_ERROR', recoverable, error: errorDetails(error) });
      if (!recoverable || attempt === maxAttempts) throw error;
      await onRetry({ attempt, kind: 'attempt-error', diagnostics: errorDetails(error) });
      continue;
    }
    const inspected = inspectLighthouseReport(completed?.lhr);
    history.push({
      attempt,
      status: inspected.status,
      diagnostics: inspected.diagnostics,
      instrumentation: sanitizeAttemptDiagnostics(completed?.attemptDiagnostics)
    });
    if (inspected.status === 'VALID') {
      return { ...inspected, completed, attempts: attempt, history };
    }
    if (attempt === maxAttempts) {
      return { ...inspected, completed, attempts: attempt, history };
    }
    await onRetry({ attempt, kind: 'incomplete-report', diagnostics: inspected.diagnostics });
  }
  throw new Error('Unreachable Lighthouse retry state');
}
