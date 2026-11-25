"""V6-02 Responsive- und Interaktionsmatrix (lokaler Dev-Server, synthetisches Konto aus UI_PROBE_USER/UI_PROBE_PASSWORD)."""
import json, os
from playwright.sync_api import sync_playwright
BASE=os.environ.get("UI_PROBE_BASE", "http://127.0.0.1:8000"); W=[320,360,390,430,768,1024,1280,1440,1920]; res=[]
with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path=os.environ.get("UI_PROBE_CHROME", "/usr/bin/google-chrome"))
    for auth in (False,True):
        for theme in ("navy","light"):
            ctx=b.new_context(); ctx.add_init_script(f"localStorage.setItem('vorneq-theme','{theme}')")
            p=ctx.new_page(); errs=[]; p.on("pageerror",lambda e: errs.append(str(e)))
            if auth:
                p.goto(BASE+"/en/accounts/login/"); p.fill("input[name=login]",os.environ.get("UI_PROBE_USER", "uxprobe")); p.fill("input[name=password]",os.environ["UI_PROBE_PASSWORD"]); p.press("input[name=password]","Enter"); p.wait_for_load_state("networkidle")
            for lang in ("fa","de","en"):
                for w in W:
                    p.set_viewport_size({"width":w,"height":860}); p.goto(f"{BASE}/{lang}/"); p.wait_for_load_state("networkidle")
                    m=p.evaluate("""()=>{const d=document.documentElement;
                      const vis=e=>{const r=e.getBoundingClientRect();const c=getComputedStyle(e);return r.width>0&&r.height>0&&c.visibility!=='hidden'};
                      const offenders=[...document.querySelectorAll('body *')].filter(e=>vis(e)&&!e.closest('.vq-sprite,.vq-side,.skip-link,.vq-sr-only')).filter(e=>{const r=e.getBoundingClientRect();return r.right>d.clientWidth+1||r.left<-1}).slice(0,4).map(e=>e.tagName+'.'+(e.getAttribute('class')||''));
                      const taps=[...document.querySelectorAll('.vq-appbar a,.vq-appbar button,.vq-appbar summary,.vq-bottom-nav__link,.vq-side__link,.vq-quick__item,.vq-composer__send')].filter(vis).map(e=>{const r=e.getBoundingClientRect();return Math.min(r.width,r.height)});
                      const bn=document.querySelector('.vq-bottom-nav');
                      return {sw:d.scrollWidth,cw:d.clientWidth,offenders,minTap:taps.length?Math.min(...taps):null,
                        bottom:getComputedStyle(bn).display,bottomItems:bn.querySelectorAll('li').length,
                        side:getComputedStyle(document.querySelector('.vq-side')).visibility,dir:d.dir,
                        hdr:document.querySelector('.vq-appbar').getBoundingClientRect().height}}""")
                    m.update(auth=auth,theme=theme,lang=lang,w=w); res.append(m)
            res.append({"errors":errs,"auth":auth,"theme":theme}); ctx.close()
    # interaction checks
    ctx=b.new_context(viewport={"width":1440,"height":900}); p=ctx.new_page(); p.goto(BASE+"/en/"); p.wait_for_load_state("networkidle")
    t=p.locator(".vq-appbar [data-vq-side-toggle]"); chk={}
    chk["desk_before"]=t.get_attribute("aria-expanded"); t.click(); chk["desk_after"]=t.get_attribute("aria-expanded")
    chk["collapsed_w"]=p.evaluate("document.querySelector('.vq-side').getBoundingClientRect().width")
    p.locator(".vq-side__link").nth(1).focus(); chk["tooltip_opacity"]=p.evaluate("getComputedStyle(document.querySelectorAll('.vq-side__link')[1].querySelector('.vq-side__label')).opacity")
    p.screenshot(path="quality/screenshots/v6-02/after/desktop-sidebar-collapsed.png")
    p.reload(); p.wait_for_load_state("networkidle"); chk["persisted"]=p.evaluate("document.documentElement.dataset.vqSide||''")
    t.click(); p.keyboard.press("/"); chk["slash_focus"]=p.evaluate("document.activeElement.id")
    p.locator("[data-vq-theme-toggle]").click(); chk["theme_after_toggle"]=p.evaluate("document.documentElement.dataset.theme+'/'+localStorage.getItem('vorneq-theme')")
    p.locator("[data-vq-theme-toggle]").click()
    p.set_viewport_size({"width":390,"height":844}); p.goto(BASE+"/fa/"); p.wait_for_load_state("networkidle")
    more=p.locator("[data-vq-more]"); more.click(); chk["drawer_vis"]=p.evaluate("getComputedStyle(document.querySelector('.vq-side')).visibility")
    chk["drawer_focus_in"]=p.evaluate("!!document.activeElement.closest('.vq-side')")
    p.screenshot(path="quality/screenshots/v6-02/after/fa-rtl-mobile-drawer.png")
    p.keyboard.press("Escape"); p.wait_for_timeout(300); chk["drawer_closed"]=p.evaluate("getComputedStyle(document.querySelector('.vq-side')).visibility"); chk["focus_back"]=p.evaluate("document.activeElement.hasAttribute('data-vq-more')")
    p.locator("#vq-ai-question").focus(); chk["bottom_hidden_typing"]=p.evaluate("getComputedStyle(document.querySelector('.vq-bottom-nav')).display")
    p.locator("#vq-ai-question").fill("SYNTHETIC test"); p.keyboard.press("Control+Enter"); p.wait_for_load_state("networkidle"); chk["submit_url"]=p.url.replace(BASE,"")
    ctx.close(); b.close()
bad=[r for r in res if "sw" in r and r["sw"]>r["cw"]]
print("measured",sum(1 for r in res if "sw" in r),"overflow",len(bad)); [print(r) for r in bad[:6]]
print("minTap",min(r["minTap"] for r in res if r.get("minTap")))
print("bottom <768 block:",all(r["bottom"]=="block" for r in res if "w" in r and r["w"]<768),"none >=768:",all(r["bottom"]=="none" for r in res if "w" in r and r["w"]>=768))
print("hdr heights",{r["hdr"] for r in res if "hdr" in r}, "bottomItems",{r["bottomItems"] for r in res if "bottomItems" in r})
print("side hidden <1024:",all(r["side"]=="hidden" for r in res if "w" in r and r["w"]<1024),"visible>=1024",all(r["side"]=="visible" for r in res if "w" in r and r["w"]>=1024))
print("errors",[r for r in res if "errors" in r and r["errors"]])
print(json.dumps(chk))
json.dump({"matrix":res,"interaction":chk},open("quality/screenshots/v6-02/after/responsive-matrix.json","w"),indent=1)
