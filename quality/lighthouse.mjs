import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import lighthouse from 'lighthouse';
import * as chromeLauncher from 'chrome-launcher';
import { chromium } from 'playwright';
import { PERF_THRESHOLDS, PROFILES, SURFACES, localizedUrl } from './contract.mjs';
import { runWithIntegrityRetries } from './lighthouse-integrity.mjs';

const outDir = process.env.QUALITY_OUT_DIR || 'artifacts/quality';
await fs.mkdir(outDir, { recursive: true });
const results = [];
let infrastructureFailure = null;

const full = SURFACES.filter(s => s.perf === 'full');
const samples = SURFACES.filter(s => s.perf === 'sample');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const LIGHTHOUSE_ATTEMPT_TIMEOUT_MS = 120000;
const LIGHTHOUSE_SETTLEMENT_GRACE_MS = 15000;

// Numeric-only process/runner snapshots; never log environment variables or URLs.
function runnerSnapshot() {
  const memory = process.memoryUsage();
  return {
    rssMiB: memory.rss / (1024 * 1024),
    heapUsedMiB: memory.heapUsed / (1024 * 1024),
    freeSystemMiB: os.freemem() / (1024 * 1024),
    loadAverage1m: os.loadavg()[0]
  };
}

class LighthouseAttemptTimeoutError extends Error {
  constructor(surface, profileName, run, series, attempt) {
    super(
      `Lighthouse attempt timed out after ${LIGHTHOUSE_ATTEMPT_TIMEOUT_MS}ms: ` +
        `${surface.id}/${profileName}/run-${run}/${series}/attempt-${attempt}`
    );
    this.name = 'LighthouseAttemptTimeoutError';
  }
}

class LighthouseAttemptCleanupError extends Error {
  constructor(message) {
    super(message);
    this.name = 'LighthouseAttemptCleanupError';
  }
}

async function waitForLighthouseToSettle(observed) {
  let graceTimer;
  try {
    return await Promise.race([
      observed,
      new Promise(resolve => {
        graceTimer = setTimeout(() => resolve(null), LIGHTHOUSE_SETTLEMENT_GRACE_MS);
      })
    ]);
  } finally {
    clearTimeout(graceTimer);
  }
}

async function waitForChrome(port, timeoutMs = 15000) {
  const endpoint = `http://127.0.0.1:${port}/json/version`;
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    try {
      const response = await fetch(endpoint);
      if (response.ok) {
        const data = await response.json();
        if (data?.webSocketDebuggerUrl) {
          return {
            browserVersion: typeof data.Browser === 'string' ? data.Browser : null,
            devtoolsProtocolVersion: typeof data['Protocol-Version'] === 'string'
              ? data['Protocol-Version'] : null
          };
        }
      }
    } catch {
      // Chrome may still be starting.
    }
    await sleep(250);
  }

  throw new Error(
    `Chrome DevTools endpoint did not become ready on port ${port} within ${timeoutMs}ms`
  );
}

async function assertTargetReachable(url, timeoutMs = 15000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      signal: controller.signal,
      redirect: 'follow'
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status} ${response.statusText}`);
    }
  } catch (error) {
    throw new Error(
      `Target URL is not reachable before Lighthouse run: ${url}\n` +
        String(error?.stack || error)
    );
  } finally {
    clearTimeout(timer);
  }
}

function isRecoverableLighthouseFailure(error) {
  if (error instanceof LighthouseAttemptCleanupError) return false;
  const message = String(error?.stack || error);
  return error instanceof LighthouseAttemptTimeoutError ||
    message.includes('Target closed') ||
    message.includes('Page.navigate') && message.includes('Protocol error');
}

async function launchChrome() {
  const start = performance.now();
  const chrome = await chromeLauncher.launch({
    chromePath: chromium.executablePath(),
    chromeFlags: [
      '--headless=new',
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
      '--no-first-run',
      '--no-default-browser-check'
    ]
  });
  const launchMs = performance.now() - start;
  try {
    const readyStart = performance.now();
    // Read only safe browser/version fields; never retain DevTools websocket URLs.
    const ready = await waitForChrome(chrome.port);
    return {
      chrome,
      launchMs,
      devtoolsReadyMs: performance.now() - readyStart,
      browserVersion: ready.browserVersion,
      devtoolsProtocolVersion: ready.devtoolsProtocolVersion
    };
  } catch (error) {
    try { await chrome.kill(); } catch { /* Preserve original startup error. */ }
    throw error;
  }
}

async function runLighthouseAttempt(surface, profileName, run, series, attempt) {
  const profile = PROFILES[profileName];
  if (!profile) throw new Error(`Unknown Lighthouse profile: ${profileName}`);
  const started = performance.now();
  const evidence = {
    nodeVersion: process.versions.node,
    browserVersion: null,
    devtoolsProtocolVersion: null,
    timingsMs: {},
    stages: {
      target: 'pending', chrome: 'not-started', devtools: 'not-started',
      lighthouse: 'not-started', cleanup: 'not-started'
    },
    traceNavigation: 'not-directly-observed',
    runnerBefore: runnerSnapshot(),
    runnerAfter: null
  };
  const url = localizedUrl('en', surface.path);
  let chrome = null;
  let chromeStopped = false;
  let primaryError = null;

  try {
    const reachabilityStarted = performance.now();
    try {
      await assertTargetReachable(url);
      evidence.stages.target = 'complete';
    } finally {
      evidence.timingsMs.targetReachabilityMs = performance.now() - reachabilityStarted;
      if (evidence.stages.target !== 'complete') evidence.stages.target = 'failed';
    }

    evidence.stages.chrome = 'pending';
    evidence.stages.devtools = 'pending';
    const launched = await launchChrome();
    chrome = launched.chrome;
    evidence.timingsMs.chromeLaunchMs = launched.launchMs;
    evidence.timingsMs.devtoolsReadyMs = launched.devtoolsReadyMs;
    evidence.browserVersion = launched.browserVersion;
    evidence.devtoolsProtocolVersion = launched.devtoolsProtocolVersion;
    evidence.stages.chrome = 'complete';
    evidence.stages.devtools = 'complete';

    const options = {
      port: chrome.port,
      output: 'json',
      logLevel: 'error',
      onlyCategories: ['performance'],
      formFactor: profile.formFactor,
      screenEmulation: profile.screenEmulation,
      throttling: profile.throttling
    };
    // A non-invasive timing measurement: no extra CDP client or trace session
    // is created, so Lighthouse alone controls navigation and trace recording.
    evidence.stages.lighthouse = 'pending';
    const invocationStarted = performance.now();
    const observed = Promise.resolve()
      .then(() => lighthouse(url, options))
      .then(
        value => ({ kind: 'success', value }),
        error => ({ kind: 'failure', error })
      );
    let timeoutTimer;
    let outcome;
    try {
      outcome = await Promise.race([
        observed,
        new Promise(resolve => {
          timeoutTimer = setTimeout(
            () => resolve({ kind: 'timeout' }),
            LIGHTHOUSE_ATTEMPT_TIMEOUT_MS
          );
        })
      ]);
    } finally {
      clearTimeout(timeoutTimer);
      evidence.timingsMs.lighthouseInvocationMs = performance.now() - invocationStarted;
    }

    if (outcome.kind === 'timeout') {
      // Existing timeout/cleanup grace and sequential retry invariant retained.
      evidence.stages.lighthouse = 'failed';
      evidence.stages.cleanup = 'pending';
      const killStart = performance.now();
      try {
        await chrome.kill();
        chromeStopped = true;
        evidence.stages.cleanup = 'complete';
      } catch (error) {
        evidence.stages.cleanup = 'failed';
        throw new LighthouseAttemptCleanupError(
          'Unable to terminate timed-out Chrome: ' + String(error?.stack || error)
        );
      } finally {
        evidence.timingsMs.chromeCleanupMs = performance.now() - killStart;
      }
      const lateOutcome = await waitForLighthouseToSettle(observed);
      if (!lateOutcome) {
        throw new LighthouseAttemptCleanupError(
          'Lighthouse remains pending after Chrome termination and ' +
            LIGHTHOUSE_SETTLEMENT_GRACE_MS + 'ms of cleanup grace'
        );
      }
      if (lateOutcome.kind === 'failure') {
        console.warn('[lighthouse] post-shutdown outcome: ' +
          (lateOutcome.error?.name || 'Error'));
      }
      throw new LighthouseAttemptTimeoutError(surface, profileName, run, series, attempt);
    }

    if (outcome.kind === 'failure') {
      evidence.stages.lighthouse = 'failed';
      throw outcome.error;
    }
    const runner = outcome.value;
    if (!runner?.lhr) {
      evidence.stages.lighthouse = 'failed';
      throw new Error('Lighthouse produced no LHR for a completed attempt');
    }
    evidence.stages.lighthouse = 'complete';
    // Direct trace-start timestamps are not exposed by this LHR: avoid claiming
    // that Lighthouse's internal navigation/trace stages were independently seen.
    evidence.traceNavigation = runner.lhr.runtimeError?.code === 'NO_NAVSTART'
      ? 'missing-no-navstart' : 'not-directly-observed';
    return { url, lhr: runner.lhr, attemptDiagnostics: evidence };
  } catch (error) {
    primaryError = error;
    error.attemptDiagnostics = evidence;
    throw error;
  } finally {
    try {
      if (chrome && !chromeStopped) {
        const killStart = performance.now();
        evidence.stages.cleanup = 'pending';
        try {
          await chrome.kill();
          evidence.stages.cleanup = 'complete';
        } catch (error) {
          evidence.stages.cleanup = 'failed';
          const cleanupFailure = new LighthouseAttemptCleanupError(
            'Chrome cleanup failed; retry is unsafe. ' +
            (primaryError ? 'Prior attempt: ' + primaryError.name + '\\n' : '') +
            String(error?.name || 'Error')
          );
          cleanupFailure.attemptDiagnostics = evidence;
          throw cleanupFailure;
        } finally {
          evidence.timingsMs.chromeCleanupMs = performance.now() - killStart;
        }
      }
    } finally {
      evidence.timingsMs.totalAttemptMs = performance.now() - started;
      evidence.runnerAfter = runnerSnapshot();
    }
  }
}

async function oneRun(surface, profileName, run, series = 'cold') {
  let measurement;
  try {
    measurement = await runWithIntegrityRetries({
      maxAttempts: 2,
      executeAttempt: async (attempt) => {
        console.log(
          `[lighthouse] start surface=${surface.id} profile=${profileName} run=${run} series=${series} attempt=${attempt}`
        );
        // runLighthouseAttempt resolves only after its own Chrome cleanup.
        return await runLighthouseAttempt(surface, profileName, run, series, attempt);
      },
      isRecoverableError: isRecoverableLighthouseFailure,
      onRetry: async ({ attempt, kind, diagnostics }) => {
        // Logs contain only rule codes and bounded numeric/enum telemetry.
        console.warn(
          `[lighthouse] retry surface=${surface.id} profile=${profileName} ` +
          `run=${run} series=${series} attempt=${attempt} kind=${kind} ` +
          JSON.stringify(diagnostics)
        );
        await sleep(1000);
      }
    });
  } catch (error) {
    throw new Error(
      `Lighthouse infrastructure failure for ${surface.id}/${profileName}/run-${run}/${series}\n` +
      String(error?.stack || error)
    );
  }

  const { completed, observed, history, attempts, status, diagnostics } = measurement;
  const { url, lhr } = completed;
  const validity = {
    status,
    attempts,
    history,
    diagnostics
  };
  if (status === 'MEASUREMENT_INVALID') {
    // A missing metric cannot support a product performance failure or success.
    // The report is uploaded, then the workflow fails the measurement-integrity gate.
    results.push({
      surface: surface.id,
      surfaceName: surface.name,
      locale: 'en',
      profile: profileName,
      run,
      series,
      url,
      lighthouseVersion: lhr?.lighthouseVersion ?? null,
      observed,
      thresholds: PERF_THRESHOLDS,
      measurementIntegrity: validity,
      productConformance: {
        lcp: 'measurement-invalid',
        cls: 'measurement-invalid',
        performanceScore: 'measurement-invalid',
        inp: PERF_THRESHOLDS.inp.classification
      }
    });
    console.error(
      `[lighthouse] MEASUREMENT_INVALID surface=${surface.id} profile=${profileName} ` +
      `run=${run} series=${series} attempts=${attempts} ` + JSON.stringify(diagnostics)
    );
    return;
  }

  const { lcpMs, cls, performanceScore } = observed;
  results.push({
    surface: surface.id,
    surfaceName: surface.name,
    locale: 'en',
    profile: profileName,
    run,
    series,
    url,
    lighthouseVersion: lhr.lighthouseVersion,
    observed,
    thresholds: PERF_THRESHOLDS,
    measurementIntegrity: validity,
    productConformance: {
      lcp: lcpMs <= PERF_THRESHOLDS.lcpMs ? 'pass' : 'fail',
      cls: cls <= PERF_THRESHOLDS.cls ? 'pass' : 'fail',
      performanceScore: performanceScore >= PERF_THRESHOLDS.lighthousePerformance ? 'pass' : 'fail',
      inp: PERF_THRESHOLDS.inp.classification
    }
  });

  console.log(
    `[lighthouse] complete surface=${surface.id} profile=${profileName} run=${run} series=${series} attempts=${attempts}`
  );
}

async function runLighthouseMeasurements() {
  for (const surface of full) {
    for (const profileName of Object.keys(PROFILES)) {
      for (let run = 1; run <= 3; run += 1) {
        await oneRun(surface, profileName, run, 'cold');
      }
    }
  }

  for (const surface of samples) {
    await oneRun(surface, 'mobile', 1, 'cold-sample');
  }
}

async function runWarmMeasurements() {
  const warmBrowser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  });

  try {
    const page = await warmBrowser.newPage({ viewport: { width: 390, height: 844 } });

    for (const surface of full) {
      const url = localizedUrl('en', surface.path);

      console.log(
        `[warm] start surface=${surface.id} url=${url}`
      );

      await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
      const started = Date.now();
      await page.reload({ waitUntil: 'networkidle', timeout: 30000 });

      results.push({
        surface: surface.id,
        surfaceName: surface.name,
        locale: 'en',
        profile: 'mobile',
        run: 1,
        series: 'warm-informational',
        url,
        observed: { reloadWallTimeMs: Date.now() - started },
        productConformance: 'informational-only'
      });

      console.log(
        `[warm] complete surface=${surface.id}`
      );
    }
  } finally {
    await warmBrowser.close();
  }
}

try {
  await runLighthouseMeasurements();
  await runWarmMeasurements();
} catch (error) {
  infrastructureFailure = String(error?.stack || error);
}

const integritySummary = {
  valid: results.filter(result => result.measurementIntegrity?.status === 'VALID').length,
  invalid: results.filter(result => result.measurementIntegrity?.status === 'MEASUREMENT_INVALID').length,
  informational: results.filter(result => result.series === 'warm-informational').length
};

const report = {
  contract: 'Global Quality Verification Specification v1.0',
  generatedAt: new Date().toISOString(),
  mode: 'report-only-product-conformance',
  note:
    'Lighthouse lab results do not establish production INP. ' +
    'INP remains blocked/unknown until field telemetry exists.',
  profiles: PROFILES,
  infrastructureFailure,
  integritySummary,
  results
};

await fs.writeFile(
  path.join(outDir, 'lighthouse-report.json'),
  JSON.stringify(report, null, 2)
);

if (infrastructureFailure) {
  console.error('\nLighthouse infrastructure failure:\n');
  console.error(infrastructureFailure);
  process.exit(2);
}

if (integritySummary.invalid > 0) {
  console.error(
    `Lighthouse measurement-integrity gate failed: ${integritySummary.invalid} of ` +
    `${integritySummary.valid + integritySummary.invalid} primary measurements invalid. ` +
    'Product threshold misses remain report-only.'
  );
  process.exit(2);
}

console.log(
  `Lighthouse verification complete: ${integritySummary.valid} valid primary measurements, ` +
  `${integritySummary.informational} warm informational; product threshold misses are report-only.`
);
