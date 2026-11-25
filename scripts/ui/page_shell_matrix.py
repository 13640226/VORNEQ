"""Browser-Messmatrix für Seitenrahmen, Navigation, Kontrast und CLS (Page Shell V2).

Nur lokal gegen einen Entwicklungsserver mit Testkonto verwenden, nie gegen
Staging/Production. Benötigt Playwright + Chromium.

  UI_PROBE_USER=... UI_PROBE_PASSWORD=... \
  python3 scripts/ui/page_shell_matrix.py http://127.0.0.1:8000 out.json \
      [--quick] [--themes=navy,light] [--langs=de,fa,en] [--widths=390,1280]
  python3 scripts/ui/page_shell_compare.py before.json after.json
"""
import os
import json
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
OUT = sys.argv[2]
QUICK = "--quick" in sys.argv
OPT = dict(a[2:].split("=",1) for a in sys.argv if a.startswith("--") and "=" in a)
THEMES = OPT.get("themes", "navy,light").split(",")
LANGS = OPT.get("langs", "de,fa,en").split(",")
ONLYW = [int(x) for x in OPT["widths"].split(",")] if "widths" in OPT else None

AUTH_PAGES = [
    "", "discover/", "orientation/", "search/", "profile/", "profile/edit/",
    "apps/home/", "apps/", "apps/workspace/", "library/", "notes/", "notes/create/",
    "documents/", "documents/create/", "marketplace/", "marketplace/seller/",
    "platform-report/", "accounts/email/", "accounts/password/change/",
]
ANON_PAGES = ["accounts/login/", "accounts/signup/", "accounts/password/reset/"]
WIDTHS = [320, 360, 390, 430, 768, 1024, 1280, 1440, 1600, 1920]
if QUICK:
    WIDTHS = [390, 1280]

GEOM_JS = r"""
() => {
  const box = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    if (!r.width && !r.height) return null;
    return [Math.round(r.left*10)/10, Math.round(r.top*10)/10, Math.round(r.width*10)/10, Math.round(r.height*10)/10];
  };
  const main = document.querySelector('.main-content') || document.querySelector('main');
  let shell = main ? main.firstElementChild : null;
  // Effektiven Rahmen finden: erstes Element, dessen Inhaltskante nicht der Viewport ist
  let probe = shell, content = null;
  for (let i = 0; probe && i < 6; i++) {
    const r = probe.getBoundingClientRect(); const cs = getComputedStyle(probe);
    const l = r.left + parseFloat(cs.paddingLeft), rr = r.right - parseFloat(cs.paddingRight);
    if (l > 0.5 || rr < document.documentElement.clientWidth - 0.5) { content = [Math.round(l*10)/10, Math.round(rr*10)/10]; break; }
    probe = probe.firstElementChild;
  }
  const h1 = main ? main.querySelector('h1') : null;
  const de = document.documentElement;
  return {
    logo: box(document.querySelector('.standalone-nav__brand, .standalone-nav__inner > :first-child')),
    nav: box(document.querySelector('.standalone-nav')),
    back: box(document.querySelector('.global-back__button')),
    h1: box(h1),
    contentEdges: content,
    overflowX: de.scrollWidth > de.clientWidth + 1,
    scrollWidth: de.scrollWidth, clientWidth: de.clientWidth,
    dir: de.getAttribute('dir'), lang: de.getAttribute('lang'),
    htmlTheme: de.getAttribute('data-theme'),
    title: document.title,
    cls: window.__cls || 0,
    firstTextTop: (() => { if (!main) return null; const w = document.createTreeWalker(main, NodeFilter.SHOW_TEXT); while (w.nextNode()) { const t = w.currentNode; if (!t.textContent.trim()) continue; const el = t.parentElement; const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); if (r.height && cs.visibility !== 'hidden' && !el.closest('[aria-hidden="true"], .visually-hidden, .sr-only, .vq-sr-only')) return Math.round(r.top*10)/10; } return null; })(),
    logoTransform: (() => { const i = document.querySelector('.standalone-nav__brand img, .standalone-nav__brand svg'); return i ? getComputedStyle(i).transform : null; })(),
  };
}
"""

CONTRAST_JS = r"""
() => {
  const parse = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const lum = ([r,g,b]) => { const f = (v) => { v/=255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); }; return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b); };
  const blend = (fg, bg) => [0,1,2].map(i => fg[i]*fg[3] + bg[i]*(1-fg[3]));
  const bgOf = (el) => {
    const stack = [];
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') return {img: true};
      const c = parse(cs.backgroundColor); if (c && c[3] > 0) { stack.push(c); if (c[3] >= 1) break; }
    }
    let base = [255,255,255];
    for (let i = stack.length - 1; i >= 0; i--) base = blend(stack[i], base);
    return {rgb: base};
  };
  const fails = []; let checked = 0, skipped = 0;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const t = walker.currentNode; if (!t.textContent.trim()) continue;
    const el = t.parentElement; if (!el || seen.has(el)) continue; seen.add(el);
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    if (!r.width || !r.height || cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) === 0) continue;
    if (el.closest('[aria-hidden="true"], .sr-only, .visually-hidden, script, style, noscript')) continue;
    const fg = parse(cs.color); const bg = bgOf(el);
    if (!fg || bg.img) { skipped++; continue; }
    const f = blend(fg, bg.rgb);
    const L1 = lum(f), L2 = lum(bg.rgb); const ratio = (Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05);
    const size = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight) >= 700;
    const large = size >= 24 || (bold && size >= 18.66);
    const need = el.matches('input::placeholder') ? 4.5 : (large ? 3 : 4.5);
    checked++;
    if (ratio < need) fails.push({text: t.textContent.trim().slice(0, 40), ratio: Math.round(ratio*100)/100, need, cls: (el.className && el.className.baseVal === undefined ? el.className : '').toString().slice(0, 40), tag: el.tagName});
  }
  return {checked, skipped, fails: fails.slice(0, 25), failCount: fails.length};
}
"""

CLS_INIT = """
window.__cls = 0;
try { new PerformanceObserver((l) => { for (const e of l.getEntries()) { if (!e.hadRecentInput) window.__cls += e.value; } }).observe({type: 'layout-shift', buffered: true}); } catch (e) {}
"""


def login(page, lang):
    page.goto(f"{BASE}/{lang}/accounts/login/")
    page.fill("input[name=login], input[name=username]", os.environ["UI_PROBE_USER"])
    page.fill("input[type=password]", os.environ["UI_PROBE_PASSWORD"])
    page.press("input[type=password]", "Enter")
    page.wait_for_load_state("networkidle")


def run():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("UI_PROBE_CHROME") or None)
        for theme in THEMES:
            for lang in LANGS:
                widths = ONLYW or (WIDTHS if (lang != "en" and theme == "navy") else [390, 1280])
                for auth in (True, False):
                    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
                    ctx.add_init_script(f"try{{localStorage.setItem('vorneq-theme','{theme}')}}catch(e){{}}")
                    ctx.add_init_script(CLS_INIT)
                    page = ctx.new_page()
                    if auth:
                        login(page, lang)
                    for w in widths:
                        page.set_viewport_size({"width": w, "height": 900})
                        for path in (AUTH_PAGES if auth else ANON_PAGES):
                            url = f"{BASE}/{lang}/{path}"
                            resp = page.goto(url)
                            page.wait_for_load_state("networkidle")
                            page.wait_for_timeout(150)
                            row = {"theme": theme, "lang": lang, "width": w, "path": path or "home",
                                   "status": resp.status if resp else None, "final": page.url.replace(BASE, "")}
                            row.update(page.evaluate(GEOM_JS))
                            if w in (390, 1280):
                                row["contrast"] = page.evaluate(CONTRAST_JS)
                            results.append(row)
                    ctx.close()
        browser.close()
    with open(OUT, "w") as fh:
        json.dump(results, fh, ensure_ascii=False)
    print(len(results), "rows ->", OUT)


if __name__ == "__main__":
    run()
