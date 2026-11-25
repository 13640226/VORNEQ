"""V6-02 Before/After-Screenshots unter identischen Bedingungen (Playwright + Chrome).

Aufruf: python3 scripts/ui/homepage_v6_02_shots.py <before|after>
Umgebung: UI_PROBE_BASE (Standard http://127.0.0.1:8000), UI_PROBE_USER, UI_PROBE_PASSWORD
(synthetisches lokales Konto), UI_PROBE_CHROME. Nur lokaler Dev-Server.
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

PHASE = sys.argv[1]
BASE = os.environ.get("UI_PROBE_BASE", "http://127.0.0.1:8000")
OUT = os.path.join(os.environ.get("UI_PROBE_OUT", "quality/screenshots/v6-02"), PHASE)
SHOTS = [  # name, lang, theme, width, height, auth
    ("desktop-dark", "en", "navy", 1440, 900, False),
    ("desktop-light", "en", "light", 1440, 900, False),
    ("mobile-dark", "en", "navy", 390, 844, False),
    ("mobile-light", "en", "light", 390, 844, False),
    ("fa-rtl-desktop", "fa", "navy", 1440, 900, False),
    ("fa-rtl-mobile", "fa", "navy", 390, 844, False),
    ("de-desktop", "de", "navy", 1440, 900, False),
    ("en-desktop", "en", "navy", 1440, 900, False),
    ("guest-homepage", "en", "navy", 1280, 800, False),
    ("auth-workspace", "en", "navy", 1440, 900, True),
    ("auth-mobile", "fa", "light", 390, 844, True),
]
METRICS_JS = """() => {
  const vh = innerHeight, q = s => document.querySelector(s);
  const box = el => { if (!el) return null; const r = el.getBoundingClientRect();
    return {top: Math.round(r.top), height: Math.round(r.height), width: Math.round(r.width)}; };
  const header = q('.vq-appbar') || q('.standalone-nav');
  const composer = q('[data-vq-composer]');
  const links = [...document.querySelectorAll('main a[href], main button')].filter(e => {
    const r = e.getBoundingClientRect(); return r.width > 0 && r.top >= 0 && r.bottom <= vh; });
  const words = (document.querySelector('main')?.innerText || '').split(/\\s+/).filter(Boolean).length;
  return {header: box(header), composer: box(composer), h1: box(q('h1')),
          sidebar: box(q('.vq-side') || q('.vq-rail')), controlsAboveFold: links.length,
          wordsInMain: words, scrollHeight: document.documentElement.scrollHeight,
          overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth};
}"""


def main():
    os.makedirs(OUT, exist_ok=True)
    metrics = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.environ.get("UI_PROBE_CHROME", "/usr/bin/google-chrome"))
        for name, lang, theme, width, height, auth in SHOTS:
            ctx = browser.new_context(viewport={"width": width, "height": height})
            ctx.add_init_script(f"localStorage.setItem('vorneq-theme','{theme}')")
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            if auth:
                page.goto(f"{BASE}/en/accounts/login/")
                page.fill("input[name=login]", os.environ.get("UI_PROBE_USER", "uxprobe"))
                page.fill("input[name=password]", os.environ["UI_PROBE_PASSWORD"])
                page.press("input[name=password]", "Enter")
                page.wait_for_load_state("networkidle")
            page.goto(f"{BASE}/{lang}/")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=os.path.join(OUT, f"{name}.png"))
            metrics[name] = page.evaluate(METRICS_JS) | {"jsErrors": errors}
            ctx.close()
        browser.close()
    with open(os.path.join(OUT, "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=1)
    for name, m in metrics.items():
        print(name, json.dumps(m))


if __name__ == "__main__":
    main()
