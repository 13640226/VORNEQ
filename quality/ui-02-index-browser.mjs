// UI-02: real Index browser and axe audit; no provider calls.
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
const BASE = process.env.BASE_URL || 'http://127.0.0.1:8766';
const DIR = process.env.SCREENSHOT_DIR || 'quality/screenshots/ui-02';
const pw = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const {chromium} = pw.default || pw;
const browser = await chromium.launch();
const results = [];
const audits = [];
function check(name, ok, detail = null) { results.push({name, ok: Boolean(ok), detail}); }
mkdirSync(DIR, {recursive:true});
try {
 for (const lang of ['fa','de','en']) {
  for (const width of [320,375,390,768,1024,1440,1920]) {
   const context = await browser.newContext({viewport:{width,height:900}});
   const page = await context.newPage();
   const errors = [], forbidden = [];
   page.on('pageerror', e => errors.push(String(e)));
   await page.route('**/*', route => {
     const u = new URL(route.request().url());
     if (u.origin !== new URL(BASE).origin || u.pathname.includes('/api/ai/')) { forbidden.push(u.pathname); return route.abort(); }
     return route.continue();
   });
   const label = lang+'-'+width;
   const res = await page.goto(BASE+'/'+lang+'/', {waitUntil:'load'});
   check(label+'-status', res.status()===200 && !!res.headers()['content-security-policy']);
   check(label+'-direction', await page.locator('html').getAttribute('dir') === (lang==='fa'?'rtl':'ltr'));
   check(label+'-single-shell', await page.locator('header.vq-header').count()===1 && await page.locator('main').count()===1 && await page.locator('h1').count()===1);
   check(label+'-overflow', await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth));
   check(label+'-guest-gate', await page.locator('a[href*="/ai/"]').count()===0);
   const input = page.locator('#vq-ix-question');
   const submit = page.locator('.vq-ix-send');
   check(label+'-empty', await submit.isDisabled());
   await page.locator('[data-vq-example]').first().click();
   check(label+'-example', (await input.inputValue()).length>0 && !(await submit.isDisabled()));
   await input.fill('');
   await page.screenshot({path:resolve(DIR,label+'.png'),fullPage:true});
   if (width===390) {
    await page.locator('[data-vq-drawer-open]').click();
    check(label+'-drawer-open',await page.locator('[data-vq-drawer-open]').getAttribute('aria-expanded')==='true');
    check(label+'-drawer-focus', await page.locator('[data-vq-drawer-close]').evaluate(el=>document.activeElement===el));
    await page.keyboard.press('Escape');
    check(label+'-drawer-close',await page.locator('[data-vq-drawer-open]').getAttribute('aria-expanded')==='false');
    check(label+'-drawer-focus-restored', await page.locator('[data-vq-drawer-open]').evaluate(el=>document.activeElement===el));
   }
   await page.keyboard.press('Control+k');
   check(label+'-palette', await page.locator('#vq-cmd').isVisible());
   await page.keyboard.press('Escape');
   check(label+'-palette-close', !(await page.locator('#vq-cmd').isVisible()));
   check(label+'-no-provider',forbidden.length===0,forbidden);
   check(label+'-js-errors',errors.length===0,errors);
   await context.close();
  }
  for (const theme of ['navy','light']) {
   for (const width of [390,1440]) {
    const ctx=await browser.newContext({viewport:{width,height:900},bypassCSP:true});
    const page=await ctx.newPage();
    await page.addInitScript(t=>localStorage.setItem('vorneq-theme',t),theme);
    await page.goto(BASE+'/'+lang+'/',{waitUntil:'load'});
    await page.addScriptTag({path:process.env.AXE_PATH});
    const r=await page.evaluate(()=>window.axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa','best-practice']}}));
    audits.push({lang,theme,width,violations:r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),incomplete:r.incomplete.map(v=>v.id),passes:r.passes.length});
    await ctx.close();
   }
  }
 }
} finally {
 await browser.close();
 writeFileSync(resolve(DIR,'browser-results.json'),JSON.stringify(results,null,2));
 writeFileSync(resolve(DIR,'axe-results.json'),JSON.stringify(audits,null,2));
}
const failed=results.filter(r=>!r.ok), violations=audits.filter(r=>r.violations.length);
console.log(JSON.stringify({checks:results.length,failed,auditScenarios:audits.length,violations},null,2));
process.exit(failed.length||violations.length?1:0);
