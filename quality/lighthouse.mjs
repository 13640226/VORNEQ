import fs from 'node:fs/promises';
import path from 'node:path';
import lighthouse from 'lighthouse';
import * as chromeLauncher from 'chrome-launcher';
import { chromium } from 'playwright';
import {
  PERF_THRESHOLDS,
  PROFILES,
  SURFACES,
  localizedUrl
} from './contract.mjs';

const outDir = process.env.QUALITY_OUT_DIR || 'artifacts/quality';

await fs.mkdir(outDir, { recursive: true });

const results = [];
let infrastructureFailure = null;

const full = SURFACES.filter((surface) => surface.perf === 'full');
const samples = SURFACES.filter((surface) => surface.perf === 'sample');

const sleep = (ms) =>
  new Promise((resolve) => setTimeout(resolve, ms));

async function waitForChrome(port, timeoutMs = 15_000) {
  const endpoint = `http://127.0.0.1:${port}/json/version`;
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    try {
      const response = await fetch(endpoint);

      if (response.ok) {
        const data = await response.json();

        if (data?.webSocketDebuggerUrl) {
          return;
        }
      }
    } catch {
      // Chrome may still be starting.
    }

    await sleep(250);
  }

  throw new Error(
    `Chrome DevTools endpoint did not become ready on port ${port} ` +
      `within ${timeoutMs}ms`
  );
}

async function assertTargetReachable(url, timeoutMs = 15_000) {
  const controller = new AbortController();

  const timer = setTimeout(
    () => controller.abort(),
    timeoutMs
  );

  try {
    const response = await fetch(url, {
      signal: controller.signal,
      redirect: 'follow'
    });

    if (!response.ok) {
      throw new Error(
        `HTTP ${response.status} ${response.statusText}`
      );
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

async function oneRun(
  chrome,
  surface,
  profileName,
  run,
  series = 'cold'
) {
  const profile = PROFILES[profileName];

  if (!profile) {
    throw new Error(
      `Unknown Lighthouse profile: ${profileName}`
    );
  }

  const url = localizedUrl('en', surface.path);

  console.log(
    `[lighthouse] start ` +
      `surface=${surface.id} ` +
      `profile=${profileName} ` +
      `run=${run} ` +
      `series=${series} ` +
      `url=${url}`
  );

  await waitForChrome(chrome.port);
  await assertTargetReachable(url);

  const options = {
    port: chrome.port,
    output: 'json',
    logLevel: 'error',
    onlyCategories: ['performance'],
    formFactor: profile.formFactor,
    screenEmulation: profile.screenEmulation,
    throttling: profile.throttling
  };

  let runner;

  try {
    runner = await lighthouse(url, options);
  } catch (error) {
    throw new Error(
      `Lighthouse infrastructure failure for ` +
        `${surface.id}/${profileName}/run-${run}/${series}\n` +
        `URL: ${url}\n` +
        String(error?.stack || error)
    );
  }

  if (!runner?.lhr) {
    throw new Error(
      `Lighthouse produced no LHR for ` +
        `${surface.id}/${profileName}/run-${run}/${series}`
    );
  }

  const lhr = runner.lhr;

  const lcp =
    lhr.audits['largest-contentful-paint']
      ?.numericValue ?? null;

  const cls =
    lhr.audits['cumulative-layout-shift']
      ?.numericValue ?? null;

  const score =
    lhr.categories.performance?.score ?? null;

  results.push({
    surface: surface.id,
    surfaceName: surface.name,
    locale: 'en',
    profile: profileName,
    run,
    series,
    url,
    lighthouseVersion: lhr.lighthouseVersion,

    observed: {
      lcpMs: lcp,
      cls,
      performanceScore: score
    },

    thresholds: PERF_THRESHOLDS,

    productConformance: {
      lcp:
        lcp !== null &&
        lcp <= PERF_THRESHOLDS.lcpMs
          ? 'pass'
          : 'fail',

      cls:
        cls !== null &&
        cls <= PERF_THRESHOLDS.cls
          ? 'pass'
          : 'fail',

      performanceScore:
        score !== null &&
        score >= PERF_THRESHOLDS.lighthousePerformance
          ? 'pass'
          : 'fail',

      inp: PERF_THRESHOLDS.inp.classification
    }
  });

  console.log(
    `[lighthouse] complete ` +
      `surface=${surface.id} ` +
      `profile=${profileName} ` +
      `run=${run} ` +
      `series=${series}`
  );
}

async function runLighthouseMeasurements() {
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

  console.log(
    `[lighthouse] Chrome launched on port ${chrome.port}`
  );

  try {
    await waitForChrome(chrome.port);

    for (const surface of full) {
      for (const profileName of Object.keys(PROFILES)) {
        for (let run = 1; run <= 3; run += 1) {
          await oneRun(
            chrome,
            surface,
            profileName,
            run,
            'cold'
          );
        }
      }
    }

    for (const surface of samples) {
      await oneRun(
        chrome,
        surface,
        'mobile',
        1,
        'cold-sample'
      );
    }
  } finally {
    console.log('[lighthouse] shutting down Chrome');

    try {
      await chrome.kill();
    } catch (error) {
      console.warn(
        '[lighthouse] Chrome cleanup failed:',
        String(error?.stack || error)
      );
    }
  }
}

async function runWarmMeasurements() {
  const warmBrowser = await chromium.launch({
    headless: true,

    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage'
    ]
  });

  try {
    const page = await warmBrowser.newPage({
      viewport: {
        width: 390,
        height: 844
      }
    });

    for (const surface of full) {
      const url = localizedUrl('en', surface.path);

      console.log(
        `[warm] start surface=${surface.id} url=${url}`
      );

      await page.goto(url, {
        waitUntil: 'networkidle',
        timeout: 30_000
      });

      const started = Date.now();

      await page.reload({
        waitUntil: 'networkidle',
        timeout: 30_000
      });

      results.push({
        surface: surface.id,
        surfaceName: surface.name,
        locale: 'en',
        profile: 'mobile',
        run: 1,
        series: 'warm-informational',
        url,

        observed: {
          reloadWallTimeMs: Date.now() - started
        },

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
  infrastructureFailure =
    String(error?.stack || error);
}

const report = {
  contract:
    'Global Quality Verification Specification v1.0',

  generatedAt: new Date().toISOString(),

  mode: 'report-only-product-conformance',

  note:
    'Lighthouse lab results do not establish production INP. ' +
    'INP remains blocked/unknown until field telemetry exists.',

  profiles: PROFILES,

  infrastructureFailure,

  results
};

await fs.writeFile(
  path.join(outDir, 'lighthouse-report.json'),
  JSON.stringify(report, null, 2)
);

if (infrastructureFailure) {
  console.error(
    '\nLighthouse infrastructure failure:\n'
  );

  console.error(infrastructureFailure);

  process.exit(2);
}

console.log(
  `Lighthouse verification complete: ` +
    `${results.length} measurements; ` +
    `product threshold misses are report-only.`
);