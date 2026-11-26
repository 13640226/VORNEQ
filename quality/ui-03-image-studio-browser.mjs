// Browser audit of Django-rendered synthetic fixtures; all requests intercepted.
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve,join} from 'node:path';
const pw=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const {chromium}=pw.default||pw;
const browser=await chromium.launch();
const dir='quality/screenshots/ui-03'; mkdirSync(dir,{recursive:true});
const results=[],audits=[];
const base='http://localhost:8769';
const csp="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'";
const image='https://synthetic.example.test/image.png';
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64');
function check(name,ok,detail=null){results.push({name,ok:!!ok,detail});}
async function setup(lang,width,theme='navy',preview=false,axe=false){
 const ctx=await browser.newContext({viewport:{width,height:900},bypassCSP:axe});
 const page=await ctx.newPage(); const errors=[],blocked=[],posts=[]; let job=null;
 await page.addInitScript(t=>localStorage.setItem('vorneq-theme',t),theme);
 page.on('pageerror',e=>errors.push(String(e)));
 await page.route('**/*',async route=>{
  const req=route.request(),u=new URL(req.url());
  const json=body=>route.fulfill({json:body});
  if(u.href===image)return route.fulfill({contentType:'image/png',body:png});
  if(u.origin!==base){blocked.push(u.origin);return route.abort();}
  if(u.pathname==='/studio')return route.fulfill({contentType:'text/html; charset=utf-8',headers:{'content-security-policy':csp},body:readFileSync(join(process.env.FIXTURES,lang+(preview?'-preview':'')+'.html'))});
  if(u.pathname.startsWith('/static/')){
   const file=resolve('staticfiles',u.pathname.slice(8));
   const types={css:'text/css',js:'application/javascript',svg:'image/svg+xml',woff2:'font/woff2',png:'image/png'};
   try{return await route.fulfill({contentType:types[file.split('.').pop()]||'application/octet-stream',body:readFileSync(file)});}catch{return route.fulfill({status:404,body:''});}
  }
  if(u.pathname.includes('/images/jobs/')){
   if(preview){blocked.push('preview-api');return route.abort();}
   if(req.method()==='POST'){const data=req.postDataJSON();posts.push(data);job={id:data.request_id,status:'queued',size:data.size};return route.fulfill({status:202,json:job});}
   if(u.pathname.endsWith('/history/'))return json({results:job?[{...job,status:'completed',created_at:'2026-11-26T00:00:00Z',mock:true}]:[],next_cursor:null,has_more:false});
   if(u.searchParams.has('active'))return json({results:[]});
   if(u.searchParams.has('latest'))return json({id:job?.id||null});
   if(u.pathname.endsWith('/download/'))return route.fulfill({contentType:'image/png',body:png});
   if(job){job={...job,status:'completed',image_url:image};return json(job);}
  }
  return route.fulfill({status:404,body:''});
 });
 const res=await page.goto(base+'/studio');
 return {ctx,page,errors,blocked,posts,res};
}
try{
 for(const lang of ['fa','de','en']){
  for(const width of [320,375,390,768,1024,1440,1920]){
   const {ctx,page,errors,blocked,posts,res}=await setup(lang,width);
   const label=lang+'-'+width;
   const prompt=page.locator('[data-vq-image-prompt]'),submit=page.locator('[data-vq-image-submit]');
   await submit.waitFor(); await page.waitForFunction(()=>!document.querySelector('[data-vq-image-submit]').disabled);
   check(label+'-csp',!!res.headers()['content-security-policy']);
   check(label+'-dir',await page.locator('html').getAttribute('dir')===(lang==='fa'?'rtl':'ltr'));
   check(label+'-shell',await page.locator('main').count()===1&&await page.locator('header.vq-header').count()===1);
   check(label+'-overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth));
   await page.screenshot({path:join(dir,label+'.png'),fullPage:true});
   await prompt.fill('Synthetic landscape');
   check(label+'-counter',await page.locator('[data-vq-image-count]').textContent()==='19');
   await page.locator('[data-vq-ratio="1536x1024"]').click();
   check(label+'-ratio',await page.locator('[data-vq-image-size]').inputValue()==='1536x1024');
   check(label+'-pressed',await page.locator('[data-vq-ratio="1536x1024"]').getAttribute('aria-pressed')==='true');
   await page.keyboard.press('Control+k');check(label+'-palette',await page.locator('#vq-cmd').isVisible());await page.keyboard.press('Escape');
   if(width===390){
    await page.locator('[data-vq-drawer-open]').click();check(label+'-drawer',await page.locator('[data-vq-drawer-open]').getAttribute('aria-expanded')==='true');await page.keyboard.press('Escape');
    await page.locator('[data-vq-image-consent]').check();await submit.click();
    await page.locator('[data-vq-image-figure]').waitFor({state:'visible',timeout:15000});
    check(label+'-one-post',posts.length===1&&posts[0].size==='1536x1024');
    await page.screenshot({path:join(dir,lang+'-completed.png'),fullPage:true});
    await page.reload();await page.locator('[data-vq-image-figure]').waitFor({state:'visible',timeout:15000});
    check(label+'-recovery',posts.length===1);
   }else check(label+'-no-post',posts.length===0);
   check(label+'-errors',errors.length===0,errors);check(label+'-blocked',blocked.length===0,blocked);
   await ctx.close();
  }
  for(const theme of ['navy','light'])for(const width of [390,1440])for(const preview of [false,true]){
   const {ctx,page,posts,blocked}=await setup(lang,width,theme,preview,true);
   if(!preview)await page.waitForFunction(()=>!document.querySelector('[data-vq-image-submit]').disabled);
   else check(lang+'-preview-'+theme+'-'+width,await page.locator('.vq-image__submit').isDisabled()&&posts.length===0&&blocked.length===0);
   await page.addScriptTag({path:process.env.AXE_PATH});
   const r=await page.evaluate(()=>axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa','best-practice']}}));
   audits.push({lang,theme,width,preview,violations:r.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),incomplete:r.incomplete.map(v=>v.id),passes:r.passes.length});
   if(width===390)await page.screenshot({path:join(dir,lang+'-'+theme+(preview?'-preview':'-active')+'.png'),fullPage:true});
   await ctx.close();
  }
 }
}finally{await browser.close();writeFileSync(join(dir,'browser-results.json'),JSON.stringify(results,null,2));writeFileSync(join(dir,'axe-results.json'),JSON.stringify(audits,null,2));}
const failed=results.filter(r=>!r.ok),violations=audits.filter(r=>r.violations.length);
console.log(JSON.stringify({checks:results.length,failed,audits:audits.length,violations},null,2));
process.exit(failed.length||violations.length?1:0);
