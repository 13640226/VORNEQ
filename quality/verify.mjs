import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';
import AxeBuilder from '@axe-core/playwright';
import { LOCALES, SURFACES, localizedUrl } from './contract.mjs';

const outDir = process.env.QUALITY_OUT_DIR || 'artifacts/quality';
await fs.mkdir(outDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const findings = [];
const coverage = [];
let infrastructureFailure = null;

function record(surface, locale, category, rule, status, observed, classification = 'product-conformance') {
  findings.push({ surface: surface.id, surfaceName: surface.name, locale, category, rule, status, observed, classification });
}

try {
  for (const surface of SURFACES) {
    for (const locale of LOCALES) {
      const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
      const page = await context.newPage();
      const url = localizedUrl(locale, surface.path);
      const response = await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
      if (!response) throw new Error(`No response for ${url}`);
      const status = response.status();
      if (status >= 500) throw new Error(`Infrastructure/navigation failure ${status} for ${url}`);
      coverage.push({ surface: surface.id, locale, url, httpStatus: status });

      const htmlLang = await page.locator('html').getAttribute('lang');
      const htmlDir = await page.locator('html').getAttribute('dir');
      const expectedDir = locale === 'fa' ? 'rtl' : 'ltr';
      record(surface, locale, 'i18n', 'html-lang', htmlLang === locale ? 'pass' : 'fail', { expected: locale, actual: htmlLang });
      record(surface, locale, 'i18n', 'html-dir', htmlDir === expectedDir ? 'pass' : 'fail', { expected: expectedDir, actual: htmlDir });

      const axe = await new AxeBuilder({ page }).analyze();
      for (const violation of axe.violations) {
        const impact = violation.impact || 'unknown';
        if (['serious', 'critical'].includes(impact)) {
          record(surface, locale, 'accessibility', violation.id, 'fail', { impact, help: violation.help, nodes: violation.nodes.length });
        }
      }
      if (!axe.violations.some(v => ['serious', 'critical'].includes(v.impact || ''))) {
        record(surface, locale, 'accessibility', 'serious-critical-count', 'pass', { count: 0 });
      }

      const meta = await page.evaluate(() => ({
        title: document.title,
        description: document.querySelector('meta[name="description"]')?.content || null,
        canonical: document.querySelector('link[rel="canonical"]')?.href || null,
        hreflang: [...document.querySelectorAll('link[rel="alternate"][hreflang]')].map(el => ({ lang: el.hreflang, href: el.href })),
        ogTitle: document.querySelector('meta[property="og:title"]')?.content || null,
        ogDescription: document.querySelector('meta[property="og:description"]')?.content || null,
        robots: document.querySelector('meta[name="robots"]')?.content || null
      }));

      record(surface, locale, 'seo', 'title', meta.title.trim() ? 'pass' : 'fail', meta.title);
      record(surface, locale, 'seo', 'description', meta.description?.trim() ? 'pass' : 'fail', meta.description);
      if (surface.seo === 'full') {
        record(surface, locale, 'seo', 'canonical', meta.canonical ? 'pass' : 'fail', meta.canonical);
        const langs = new Set(meta.hreflang.map(x => x.lang));
        const missing = LOCALES.filter(l => !langs.has(l));
        record(surface, locale, 'seo', 'hreflang-fa-en-de', missing.length === 0 ? 'pass' : 'fail', { missing, alternates: meta.hreflang });
      } else {
        record(surface, locale, 'seo', 'indexability-policy', 'blocked/unknown', 'Account/auth indexability policy is intentionally not invented.', 'blocked/unknown');
      }

      if (surface.id === 'V-01') {
        record(surface, locale, 'seo', 'open-graph-title', meta.ogTitle ? 'pass' : 'fail', meta.ogTitle);
        record(surface, locale, 'seo', 'open-graph-description', meta.ogDescription ? 'pass' : 'fail', meta.ogDescription);
      }

      record(surface, locale, 'accessibility', 'keyboard-focus-order', 'manual-required', 'Requires manual keyboard-only verification.', 'manual');
      record(surface, locale, 'accessibility', 'focus-visibility', 'manual-required', 'Requires manual visual focus verification.', 'manual');
      record(surface, locale, 'accessibility', 'reflow-200-400', 'manual-required', 'Requires manual 200%/400% zoom/reflow verification.', 'manual');
      record(surface, locale, 'accessibility', 'reduced-motion', 'hybrid-required', 'Automated presence is insufficient to prove acceptable reduced-motion behavior.', 'hybrid');

      await context.close();
    }
  }

  const browserContext = await browser.newContext();
  const robotsResponse = await browserContext.request.get(`${process.env.QUALITY_BASE_URL || 'http://127.0.0.1:8000'}/robots.txt`);
  record({ id: 'GLOBAL', name: 'Global crawl infrastructure' }, 'all', 'seo', 'robots.txt', robotsResponse.ok() ? 'pass' : 'fail', { status: robotsResponse.status() });
  const sitemapResponse = await browserContext.request.get(`${process.env.QUALITY_BASE_URL || 'http://127.0.0.1:8000'}/sitemap.xml`);
  record({ id: 'GLOBAL', name: 'Global crawl infrastructure' }, 'all', 'seo', 'sitemap.xml', sitemapResponse.ok() ? 'pass' : 'fail', { status: sitemapResponse.status() });
  await browserContext.close();
} catch (error) {
  infrastructureFailure = String(error?.stack || error);
} finally {
  await browser.close();
}

const report = {
  contract: 'Global Quality Verification Specification v1.0',
  mode: 'report-only-product-conformance',
  generatedAt: new Date().toISOString(),
  disclaimer: 'axe findings are evidence only and do not establish full WCAG conformance.',
  infrastructureFailure,
  coverage,
  findings
};

await fs.writeFile(path.join(outDir, 'verification-report.json'), JSON.stringify(report, null, 2));
await fs.writeFile(path.join(outDir, 'verification-summary.txt'), [
  `Infrastructure: ${infrastructureFailure ? 'FAIL' : 'PASS'}`,
  `Surfaces/locales exercised: ${coverage.length}`,
  `Product findings recorded: ${findings.filter(f => f.status === 'fail').length}`,
  'Product-conformance findings are report-only in Infrastructure v1.',
  'axe output is evidence only; manual WCAG verification remains required.'
].join('\n') + '\n');

if (infrastructureFailure) {
  console.error(infrastructureFailure);
  process.exit(2);
}
console.log(`Verification complete; ${findings.filter(f => f.status === 'fail').length} report-only product findings recorded.`);
