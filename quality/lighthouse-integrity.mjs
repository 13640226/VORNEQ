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
    resources: {
      before: sanitizeRunner(data.runnerBefore),
      after: sanitizeRunner(data.runnerAfter)
    }
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
        lighthouseReportedTotalMs: safeNumber(lhr?.timing?.total, 180000),
        // Bounded, numeric-only Lighthouse phase timings help distinguish
        // navigation/trace failures without exposing URLs or page contents.
        phases: (Array.isArray(lhr?.timing?.entries) ? lhr.timing.entries : [])
          .filter(entry => typeof entry?.name === 'string' &&
            /^[a-zA-Z][a-zA-Z0-9_-]{0,63}$/.test(entry.name))
          .slice(0, 20)
          .map(entry => ({
            name: entry.name,
            durationMs: safeNumber(entry.duration, 180000)
          }))
      },
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
  if (!Number.isInteger(maxAttempts) || maxAttempts < 1 || maxAttempts > 3) {
    throw new RangeError('Lighthouse attempts must be between 1 and 3');
  }
  const history = [];
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    let completed;
    try {
      completed = await executeAttempt(attempt);
    } catch (error) {
      const recoverable = isRecoverableError(error);
      history.push({ attempt, status: 'ATTEMPT_ERROR', recoverable, error: errorDetails(error) });
      if (!recoverable || attempt >= Math.min(maxAttempts, 2)) throw error;
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
    if (attempt === maxAttempts ||
        (attempt >= 2 && inspected.diagnostics.runtimeError?.code !== 'NO_NAVSTART')) {
      return { ...inspected, completed, attempts: attempt, history };
    }
    await onRetry({ attempt, kind: 'incomplete-report', diagnostics: inspected.diagnostics });
  }
  throw new Error('Unreachable Lighthouse retry state');
}
