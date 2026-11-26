// UI-01 App Shell V8 – Browserprüfung mit Playwright (Chromium).
// Aufruf: BASE_URL=http://127.0.0.1:8765 node quality/ui-01-shell-browser.mjs
// Optional: PLAYWRIGHT_MODULE=/pfad/zu/playwright/index.mjs, SCREENSHOT_DIR=quality/screenshots/ui-01
// Ergebnis: JSON pro Prüfung; Exit-Code 1, sobald eine Prüfung fehlschlägt.
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8765').replace(/\/$/, '');
const SHOTS = process.env.SCREENSHOT_DIR || '';
const pw = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const { chromium } = pw.default || pw;

const results = [];
function check(name, ok, detail) {
  results.push({ name, ok: Boolean(ok), detail: detail ?? null });
}

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH || undefined,
});

async function openPage({ lang = 'fa', width = 1280, height = 800, theme = null } = {}) {
  const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const problems = { console: [], csp: [], pageErrors: [] };
  page.on('console', (msg) => {
    if (msg.type() === 'error') problems.console.push(msg.text());
  });
  page.on('pageerror', (err) => problems.pageErrors.push(String(err)));
  await page.addInitScript(({ theme }) => {
    if (theme) {
      try { localStorage.setItem('vorneq-theme', theme); } catch (e) { /* ignore */ }
    }
    window.__vqCsp = [];
    document.addEventListener('securitypolicyviolation', (e) => {
      window.__vqCsp.push(`${e.violatedDirective} ${e.blockedURI}`);
    });
    // Theme zum Zeitpunkt, an dem <body> entsteht (= vor dem ersten Paint des Inhalts).
    new MutationObserver((records, obs) => {
      if (document.body) {
        window.__vqThemeAtBody = document.documentElement.dataset.theme || null;
        obs.disconnect();
      }
    }).observe(document, { childList: true, subtree: true });
  }, { theme });
  const response = await page.goto(`${BASE}/${lang}/shell-test/`, { waitUntil: 'load' });
  return { context, page, response, problems };
}

async function overflowX(page) {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

async function shot(page, name) {
  if (!SHOTS) return;
  mkdirSync(resolve(SHOTS), { recursive: true });
  await page.screenshot({ path: resolve(SHOTS, name), fullPage: false });
}

// ---------- Desktop, Persisch (RTL) ----------
{
  const { context, page, response, problems } = await openPage({ lang: 'fa' });
  check('desktop_fa_status_200', response.status() === 200, response.status());
  check('csp_header_present', Boolean(response.headers()['content-security-policy']));
  const dir = await page.evaluate(() => [document.documentElement.lang, document.documentElement.dir]);
  check('rtl_html_attributes', dir[0] === 'fa' && dir[1] === 'rtl', dir);
  const sidebar = await page.locator('#vq-sidebar').boundingBox();
  const vw = 1280;
  check('desktop_sidebar_visible_on_right_in_rtl', sidebar && sidebar.x + sidebar.width >= vw - 1 && sidebar.width > 200, sidebar);
  check('desktop_menu_button_hidden', !(await page.locator('[data-vq-drawer-open]').isVisible()));
  check('desktop_no_horizontal_overflow', (await overflowX(page)) <= 0, await overflowX(page));
  check('desktop_bottomnav_hidden', !(await page.locator('.vq-bottomnav').isVisible()));
  await shot(page, 'desktop-fa-dark.png');

  // Befehlspalette per Tastatur
  await page.keyboard.press('Control+k');
  const opened = await page.locator('[data-vq-cmd]').isVisible();
  const focusedId = await page.evaluate(() => document.activeElement && document.activeElement.id);
  const ad1 = await page.getAttribute('#vq-cmd-input', 'aria-activedescendant');
  const sel1 = ad1 ? await page.getAttribute(`#${ad1}`, 'aria-selected') : null;
  await page.keyboard.press('ArrowDown');
  const ad2 = await page.getAttribute('#vq-cmd-input', 'aria-activedescendant');
  const sel2 = ad2 ? await page.getAttribute(`#${ad2}`, 'aria-selected') : null;
  const prevSel = ad1 ? await page.getAttribute(`#${ad1}`, 'aria-selected') : null;
  await page.keyboard.press('ArrowUp');
  await page.keyboard.press('ArrowUp');
  const adWrap = await page.getAttribute('#vq-cmd-input', 'aria-activedescendant');
  const optionCount = await page.locator('#vq-cmd-list [role="option"]').count();
  check('cmd_opens_with_ctrl_k', opened);
  check('cmd_input_focused', focusedId === 'vq-cmd-input', focusedId);
  check('cmd_activedescendant_first', ad1 === 'vq-cmd-opt-0' && sel1 === 'true', { ad1, sel1 });
  check('cmd_activedescendant_arrowdown', ad2 === 'vq-cmd-opt-1' && sel2 === 'true' && prevSel === 'false', { ad2, sel2, prevSel });
  check('cmd_activedescendant_wraps', adWrap === `vq-cmd-opt-${optionCount - 1}`, { adWrap, optionCount });
  await page.fill('#vq-cmd-input', 'بازارچه');
  const filtered = await page.locator('#vq-cmd-list [role="option"]').allTextContents();
  check('cmd_filters_options', filtered.length === 1 && filtered[0].includes('بازارچه'), filtered);
  await page.fill('#vq-cmd-input', 'zzzz-no-match');
  check('cmd_empty_state', await page.locator('[data-vq-cmd-empty]').isVisible()
    && (await page.getAttribute('#vq-cmd-input', 'aria-activedescendant')) === '');
  await page.fill('#vq-cmd-input', '');
  await shot(page, 'desktop-fa-command-palette.png');
  await page.keyboard.press('Escape');
  check('cmd_closes_with_escape', !(await page.locator('[data-vq-cmd]').isVisible()));

  // Enter navigiert zum aktiven Eintrag
  await page.keyboard.press('Control+k');
  await page.fill('#vq-cmd-input', 'اسناد');
  await Promise.all([page.waitForURL(/\/documents\//, { timeout: 5000 }).catch(() => null), page.keyboard.press('Enter')]);
  check('cmd_enter_navigates', /\/fa\/documents\//.test(page.url()), page.url());

  const csp = await page.evaluate(() => window.__vqCsp || []);
  check('desktop_no_csp_violations', csp.length === 0, csp);
  check('desktop_no_console_errors', problems.console.length === 0 && problems.pageErrors.length === 0, problems);
  await context.close();
}

// ---------- Theme ohne Flackern + Umschalter ----------
{
  const { context, page } = await openPage({ lang: 'fa', theme: 'light' });
  const atBody = await page.evaluate(() => window.__vqThemeAtBody);
  check('theme_applied_before_body', atBody === 'light', atBody);
  const pressed = await page.getAttribute('[data-theme-option="light"]', 'aria-pressed');
  check('theme_button_reflects_preference', pressed === 'true', pressed);
  await shot(page, 'desktop-fa-light.png');
  await page.click('[data-theme-option="dark"]');
  const after = await page.evaluate(() => [document.documentElement.dataset.theme, localStorage.getItem('vorneq-theme')]);
  check('theme_toggle_dark_persists', after[0] === 'dark' && after[1] === 'dark', after);
  const bg = await page.evaluate(() => {
    const probe = document.createElement('div');
    probe.className = 'vq-visually-hidden';
    probe.setAttribute('data-probe', '');
    document.body.appendChild(probe);
    probe.classList.add('vq-shell-body');
    const expected = getComputedStyle(probe).backgroundColor;
    probe.remove();
    return { actual: getComputedStyle(document.body).backgroundColor, expected };
  });
  check('theme_dark_background_applied', bg.actual === bg.expected && bg.actual !== 'rgba(0, 0, 0, 0)', bg);
  await context.close();
}

// ---------- Mobil, Persisch (RTL) ----------
{
  const W = 390;
  const { context, page, problems } = await openPage({ lang: 'fa', width: W, height: 844 });
  const closed = await page.locator('#vq-sidebar').boundingBox();
  check('mobile_rtl_drawer_closed_offscreen_right', closed && closed.x >= W - 1, closed);
  check('mobile_drawer_closed_not_focusable', !(await page.locator('#vq-sidebar').isVisible()));
  const main = await page.locator('#vq-main').boundingBox();
  check('mobile_single_column', main && Math.abs(main.width - W) <= 1 && main.x <= 1, main);
  check('mobile_no_horizontal_overflow', (await overflowX(page)) <= 0, await overflowX(page));
  check('mobile_bottomnav_visible', await page.locator('.vq-bottomnav').isVisible());
  const cols = await page.evaluate(() => getComputedStyle(document.querySelector('.vq-preview__grid')).gridTemplateColumns.split(' ').length);
  check('mobile_cards_single_column', cols === 1, cols);
  const small = await page.evaluate(() => Array.from(document.querySelectorAll('.vq-header a, .vq-header button, .vq-bottomnav a, .vq-bottomnav button'))
    .filter((el) => el.offsetParent !== null)
    .map((el) => { const r = el.getBoundingClientRect(); return { c: el.className, w: r.width, h: r.height }; })
    .filter((r) => r.w < 44 || r.h < 44));
  check('mobile_targets_44px', small.length === 0, small);
  await shot(page, 'mobile-fa-closed.png');

  await page.click('[data-vq-drawer-open]');
  await page.waitForTimeout(350);
  const open = await page.locator('#vq-sidebar').boundingBox();
  const expanded = await page.getAttribute('[data-vq-drawer-open]', 'aria-expanded');
  const focusIn = await page.evaluate(() => document.getElementById('vq-sidebar').contains(document.activeElement));
  check('mobile_drawer_opens', expanded === 'true' && open && Math.abs(open.x + open.width - W) <= 1, { expanded, open });
  check('mobile_drawer_focus_moves_in', focusIn);
  check('mobile_scrim_visible', await page.locator('[data-vq-scrim]').isVisible());
  for (let i = 0; i < 12; i += 1) await page.keyboard.press('Tab');
  const stillIn = await page.evaluate(() => document.getElementById('vq-sidebar').contains(document.activeElement));
  await page.keyboard.press('Shift+Tab');
  const stillInBack = await page.evaluate(() => document.getElementById('vq-sidebar').contains(document.activeElement));
  check('mobile_drawer_focus_trap', stillIn && stillInBack, { stillIn, stillInBack });
  await shot(page, 'mobile-fa-drawer-open.png');
  await page.keyboard.press('Escape');
  await page.waitForTimeout(350);
  const after = await page.getAttribute('[data-vq-drawer-open]', 'aria-expanded');
  const focusBack = await page.evaluate(() => document.activeElement && document.activeElement.hasAttribute('data-vq-drawer-open'));
  check('mobile_drawer_escape_closes_and_restores_focus', after === 'false' && focusBack, { after, focusBack });
  await page.click('[data-vq-drawer-open]');
  await page.waitForTimeout(350);
  await page.mouse.click(10, 400);
  await page.waitForTimeout(350);
  check('mobile_drawer_scrim_click_closes', (await page.getAttribute('[data-vq-drawer-open]', 'aria-expanded')) === 'false');

  await page.click('.vq-bottomnav button[data-vq-cmd-open]');
  check('mobile_bottomnav_opens_palette', await page.locator('[data-vq-cmd]').isVisible());
  await shot(page, 'mobile-fa-command-palette.png');
  await page.keyboard.press('Escape');
  const csp = await page.evaluate(() => window.__vqCsp || []);
  check('mobile_no_csp_violations', csp.length === 0, csp);
  check('mobile_no_console_errors', problems.console.length === 0 && problems.pageErrors.length === 0, problems);
  await context.close();
}

// ---------- Mobil, Deutsch (LTR) ----------
{
  const W = 390;
  const { context, page } = await openPage({ lang: 'de', width: W, height: 844 });
  const closed = await page.locator('#vq-sidebar').boundingBox();
  check('mobile_ltr_drawer_closed_offscreen_left', closed && closed.x + closed.width <= 1, closed);
  await page.click('[data-vq-drawer-open]');
  await page.waitForTimeout(350);
  const open = await page.locator('#vq-sidebar').boundingBox();
  check('mobile_ltr_drawer_opens_from_left', open && Math.abs(open.x) <= 1, open);
  await shot(page, 'mobile-de-drawer-open.png');
  await context.close();
}

// ---------- Bestehende Routen unverändert ----------
// Vergleicht Statuscodes mit einem Server auf dem Stand von main (BASELINE_URL).
// Ohne BASELINE_URL gilt: jede Route < 400 (anonym; 302 = Login-Weiterleitung).
{
  const context = await browser.newContext();
  const BASELINE = (process.env.BASELINE_URL || '').replace(/\/$/, '');
  const paths = ['/fa/', '/de/', '/fa/discover/', '/fa/discover/knowledge/', '/fa/marketplace/', '/fa/search/',
    '/api/ai/v1/chat/?lang=fa', '/fa/accounts/login/', '/fa/documents/', '/fa/notes/', '/fa/apps/home/'];
  const statuses = {};
  for (const p of paths) {
    const r = await context.request.get(`${BASE}${p}`, { maxRedirects: 0 });
    const entry = { branch: r.status() };
    if (BASELINE) entry.main = (await context.request.get(`${BASELINE}${p}`, { maxRedirects: 0 })).status();
    statuses[p] = entry;
  }
  const broken = Object.entries(statuses).filter(([, e]) => (BASELINE ? e.branch !== e.main : e.branch >= 400));
  check(BASELINE ? 'existing_routes_same_status_as_main' : 'existing_routes_below_400', broken.length === 0, statuses);
  await context.close();
}

await browser.close();
const failed = results.filter((r) => !r.ok);
console.log(JSON.stringify({ base: BASE, total: results.length, failed: failed.length, results }, null, 2));
process.exit(failed.length ? 1 : 0);
