// UI-01 App Shell V8 – axe-core Prüfung (WCAG 2.0/2.1/2.2 A+AA) in mehreren Zuständen.
// Aufruf: BASE_URL=http://127.0.0.1:8765 AXE_PATH=/pfad/axe.min.js node quality/ui-01-shell-axe.mjs
// bypassCSP gilt nur für diesen Prüf-Kontext, damit axe injiziert werden kann; die
// CSP der Anwendung selbst prüft quality/ui-01-shell-browser.mjs ohne Bypass.
const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8765').replace(/\/$/, '');
const AXE = process.env.AXE_PATH;
if (!AXE) { console.error('AXE_PATH fehlt'); process.exit(2); }
const pw = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const { chromium } = pw.default || pw;
const browser = await chromium.launch();

const scenarios = [];
for (const lang of ['fa', 'de', 'en']) {
  for (const theme of ['navy', 'light']) {
    scenarios.push({ lang, theme, width: 1280, state: 'default' });
    scenarios.push({ lang, theme, width: 390, state: 'default' });
  }
  scenarios.push({ lang, theme: 'navy', width: 390, state: 'drawer' });
  scenarios.push({ lang, theme: 'navy', width: 1280, state: 'palette' });
  scenarios.push({ lang, theme: 'light', width: 390, state: 'language' });
}

const out = [];
for (const sc of scenarios) {
  const context = await browser.newContext({ viewport: { width: sc.width, height: 860 }, bypassCSP: true });
  const page = await context.newPage();
  await page.addInitScript((t) => { try { localStorage.setItem('vorneq-theme', t); } catch (e) { /* */ } }, sc.theme);
  await page.goto(`${BASE}/${sc.lang}/shell-test/`, { waitUntil: 'load' });
  if (sc.state === 'drawer') { await page.click('[data-vq-drawer-open]'); await page.waitForTimeout(350); }
  if (sc.state === 'palette') { await page.keyboard.press('Control+k'); }
  if (sc.state === 'language') { await page.click('[data-vq-lang] summary'); }
  await page.addScriptTag({ path: AXE });
  const res = await page.evaluate(async () => window.axe.run(document, {
    runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] },
  }));
  out.push({
    ...sc,
    violations: res.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.map((n) => n.target.join(' ')).slice(0, 5) })),
    incomplete: res.incomplete.map((v) => v.id),
    passes: res.passes.length,
  });
  await context.close();
}
await browser.close();
const failed = out.filter((r) => r.violations.length);
console.log(JSON.stringify({ base: BASE, scenarios: out.length, withViolations: failed.length, results: out }, null, 2));
process.exit(failed.length ? 1 : 0);
