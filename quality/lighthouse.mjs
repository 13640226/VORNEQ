import fs from 'node:fs/promises';
import path from 'node:path';
import lighthouse from 'lighthouse';
import * as chromeLauncher from 'chrome-launcher';
import { chromium } from 'playwright';
import { PERF_THRESHOLDS, PROFILES, SURFACES, localizedUrl } from './contract.mjs';

const outDir = process.env.QUALITY_OUT_DIR || 'artifacts/quality';
await fs.mkdir(outDir, { recursive: true });
const results = [];
let infrastructureFailure = null;

const full = SURFACES.filter(s => s.perf === 'full');
const samples = SURFACES.filter(s => s.perf === 'sample');

async function oneRun(surface, profileName, run, series = 'cold') {
  const chrome = await chromeLauncher.launch({ chromePath: chromium.executablePath(), chromeFlags: ['--headless', '--no-sandbox', '--disable-gpu'] });
  try {
    const options = {
      port: chrome.port,
      output: 'json',
      logLevel: 'error',
      onlyCategories: ['performance'],
      formFactor: PROFILES[profileName].formFactor,
      screenEmulation: PROFILES[profileName].screenEmulation,
      throttling: PROFILES[profileName].throttling
    };
    const url = localizedUrl('en', surface.path);
    const runner = await lighthouse(url, options);
    if (!runner?.lhr) throw new Error(`Lighthouse produced no LHR for ${surface.id}/${profileName}`);
    const lhr = runner.lhr;
    const lcp = lhr.audits['largest-contentful-paint']?.numericValue ?? null;
    const cls = lhr.audits['cumulative-layout-shift']?.numericValue ?? null;
    const score = lhr.categories.performance?.score ?? null;
    results.push({
      surface: surface.id,
      surfaceName: surface.name,
      locale: 'en',
      profile: profileName,
      run,
      series,
      url,
      lighthouseVersion: lhr.lighthouseVersion,
      observed: { lcpMs: lcp, cls, performanceScore: score },
      thresholds: PERF_THRESHOLDS,
      productConformance: {
        lcp: lcp !== null && lcp <= PERF_THRESHOLDS.lcpMs ? 'pass' : 'fail',
        cls: cls !== null && cls <= PERF_THRESHOLDS.cls ? 'pass' : 'fail',
        performanceScore: score !== null && score >= PERF_THRESHOLDS.lighthousePerformance ? 'pass' : 'fail',
        inp: PERF_THRESHOLDS.inp.classification
      }
    });
  } finally {
    await chrome.kill();
  }
}

try {
  for (const surface of full) {
    for (const profileName of Object.keys(PROFILES)) {
      for (let run = 1; run <= 3; run += 1) await oneRun(surface, profileName, run, 'cold');
    }
  }
  for (const surface of samples) await oneRun(surface, 'mobile', 1, 'cold-sample');

  const warmBrowser = await chromium.launch({ headless: true });
  try {
    const page = await warmBrowser.newPage({ viewport: { width: 390, height: 844 } });
    for (const surface of full) {
      const url = localizedUrl('en', surface.path);
      await page.goto(url, { waitUntil: 'networkidle' });
      const started = Date.now();
      await page.reload({ waitUntil: 'networkidle' });
      results.push({ surface: surface.id, surfaceName: surface.name, locale: 'en', profile: 'mobile', run: 1, series: 'warm-informational', url, observed: { reloadWallTimeMs: Date.now() - started }, productConformance: 'informational-only' });
    }
  } finally {
    await warmBrowser.close();
  }
} catch (error) {
  infrastructureFailure = String(error?.stack || error);
}

const report = {
  contract: 'Global Quality Verification Specification v1.0',
  generatedAt: new Date().toISOString(),
  mode: 'report-only-product-conformance',
  note: 'Lighthouse lab results do not establish production INP. INP remains blocked/unknown until field telemetry exists.',
  profiles: PROFILES,
  infrastructureFailure,
  results
};
await fs.writeFile(path.join(outDir, 'lighthouse-report.json'), JSON.stringify(report, null, 2));

if (infrastructureFailure) {
  console.error(infrastructureFailure);
  process.exit(2);
}
console.log(`Lighthouse verification complete: ${results.length} measurements; product threshold misses are report-only.`);
