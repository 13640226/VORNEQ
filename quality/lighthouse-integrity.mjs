// Pure Lighthouse measurement validation and safe, bounded retry orchestration.
// Product threshold decisions are deliberately separate from measurement integrity.
const METRICS = [
  ['lcpMs', 'largest-contentful-paint'],
  ['cls', 'cumulative-layout-shift'],
  ['performanceScore', null]
];

function clipped(value) {
  return value == null ? null : String(value).slice(0, 500);
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
        ? { code: clipped(lhr.runtimeError.code), message: clipped(lhr.runtimeError.message) }
        : null,
      runtimeWarnings: (Array.isArray(lhr?.runWarnings) ? lhr.runWarnings : []).slice(0, 10).map(clipped),
      audits: {
        'largest-contentful-paint': auditDetails(lcp),
        'cumulative-layout-shift': auditDetails(cls)
      },
      performanceCategoryScore: observed.performanceScore
    }
  };
}

function errorDetails(error) {
  return { name: clipped(error?.name), message: clipped(error?.message ?? error) };
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
    history.push({ attempt, status: inspected.status, diagnostics: inspected.diagnostics });
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
