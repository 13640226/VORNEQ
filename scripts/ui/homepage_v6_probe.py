"""V6-01 homepage probe: overflow at 8 widths x 3 languages x 2 themes x guest/auth, tablet toggle, screenshots.

Local dev server only. Credentials come from UI_PROBE_USER / UI_PROBE_PASSWORD (synthetic local account).
"""
import json, os, sys
from playwright.sync_api import sync_playwright
BASE=os.environ.get("UI_PROBE_BASE", "http://127.0.0.1:8000"); OUT=os.environ.get("UI_PROBE_OUT", "quality/screenshots/v6")
WIDTHS=[320,360,390,430,768,1024,1440,1920]
res={"overflow":[], "checks":{}}
def login(ctx):
    p=ctx.new_page(); p.goto(BASE+"/en/accounts/login/")
    p.fill("input[name=login]",os.environ.get("UI_PROBE_USER", "uxprobe")); p.fill("input[name=password]",os.environ["UI_PROBE_PASSWORD"]); p.press("input[name=password]","Enter")
    p.wait_for_load_state("networkidle"); p.close()
with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path=os.environ.get("UI_PROBE_CHROME", "/usr/bin/google-chrome"))
    for auth in (False,True):
      for theme in ("navy","light"):
        ctx=b.new_context(); ctx.add_init_script(f"localStorage.setItem('vorneq-theme','{theme}')")
        if auth: login(ctx)
        p=ctx.new_page()
        for lang in ("fa","de","en"):
          for w in WIDTHS:
            p.set_viewport_size({"width":w,"height":900}); p.goto(f"{BASE}/{lang}/"); p.wait_for_load_state("networkidle")
            m=p.evaluate("""()=>{const d=document.documentElement;const bn=document.querySelector('.vq-bottom-nav');
              const links=[...document.querySelectorAll('.vq-bottom-nav__link')].map(a=>a.getBoundingClientRect()).filter(r=>r.width>0);
              const t=document.querySelector('[data-vq-sidebar-toggle]');
              const wide=[...document.querySelectorAll('body *')].filter(e=>{const r=e.getBoundingClientRect();return r.right>d.clientWidth+1||r.left<-1}).filter(e=>!e.closest('.vq-sprite,.skip-link,.vq-sr-only')).slice(0,5).map(e=>e.className&&e.className.baseVal===undefined?e.tagName+'.'+e.className:e.tagName);
              return {sw:d.scrollWidth,cw:d.clientWidth,bottom:bn?getComputedStyle(bn).display:null,
                minTap:links.length?Math.min(...links.map(r=>Math.min(r.width,r.height))):null,nlinks:links.length,
                toggle:t?getComputedStyle(t).display:null,rail:getComputedStyle(document.querySelector('.vq-rail')).display,
                dir:d.dir,wide}}""")
            m.update(auth=auth,theme=theme,lang=lang,w=w); res["overflow"].append(m)
        if not auth:
            for lang,w,name in (("en",1440,"desktop"),("en",390,"mobile")):
                p.set_viewport_size({"width":w,"height":900}); p.goto(f"{BASE}/{lang}/"); p.wait_for_load_state("networkidle")
                p.screenshot(path=f"{OUT}/{name}-{'dark' if theme=='navy' else 'light'}.png", full_page=(w<500))
            if theme=="navy":
                for lang,w,name in (("fa",390,"fa-rtl-mobile"),("fa",1440,"fa-rtl-desktop"),("de",1440,"de-desktop"),("en",1024,"en-desktop-1024")):
                    p.set_viewport_size({"width":w,"height":900}); p.goto(f"{BASE}/{lang}/"); p.wait_for_load_state("networkidle")
                    p.screenshot(path=f"{OUT}/{name}.png")
        else:
            if theme=="navy":
                p.set_viewport_size({"width":820,"height":1000}); p.goto(f"{BASE}/en/"); p.wait_for_load_state("networkidle")
                t=p.locator("[data-vq-sidebar-toggle]"); before=t.get_attribute("aria-expanded")
                hidden_before=p.evaluate("getComputedStyle(document.querySelector('.vq-rail__lists')).display")
                t.click(); after=t.get_attribute("aria-expanded")
                shown=p.evaluate("getComputedStyle(document.querySelector('.vq-rail__lists')).display")
                p.locator(".vq-rail__link").first.focus(); p.keyboard.press("Escape")
                esc=t.get_attribute("aria-expanded"); focused=p.evaluate("document.activeElement.hasAttribute('data-vq-sidebar-toggle')")
                t.click(); t.scroll_into_view_if_needed(); p.screenshot(path=f"{OUT}/tablet-sidebar-open-auth.png")
                res["checks"]["tablet_toggle"]=dict(before=before,hidden_before=hidden_before,after=after,shown=shown,esc=esc,focus_returned=focused)
                p.set_viewport_size({"width":390,"height":900}); p.goto(f"{BASE}/en/"); p.wait_for_load_state("networkidle")
                p.screenshot(path=f"{OUT}/mobile-dark-auth.png")
                # bottom nav must not cover page end
                p.evaluate("window.scrollTo(0,document.body.scrollHeight)")
                res["checks"]["footer_clear"]=p.evaluate("""()=>{const bn=document.querySelector('.vq-bottom-nav').getBoundingClientRect();
                   const last=[...document.querySelectorAll('main *, footer *')].filter(e=>!e.closest('.vq-bottom-nav')&&e.getBoundingClientRect().height>0).pop().getBoundingClientRect();
                   return {navTop:bn.top,lastBottom:last.bottom}}""")
        ctx.close()
    b.close()
json.dump(res,open(OUT + "/measurements.json","w"),indent=1)
bad=[r for r in res["overflow"] if r["sw"]>r["cw"]]
print("measurements",len(res["overflow"]),"overflow",len(bad))
for r in bad[:10]: print(r)
mob=[r for r in res["overflow"] if r["w"]<768]
print("bottom visible <768:",all(r["bottom"]=="block" for r in mob),"hidden >=768:",all(r["bottom"]=="none" for r in res["overflow"] if r["w"]>=768))
print("min tap mobile:",min(r["minTap"] for r in mob),"links:",sorted({r["nlinks"] for r in mob}))
print("toggle tablet:",{(r["w"],r["toggle"]) for r in res["overflow"]})
print("rail:",{(r["w"],r["rail"]) for r in res["overflow"]})
print("dir fa:",{r["dir"] for r in res["overflow"] if r["lang"]=="fa"})
print(res["checks"])
