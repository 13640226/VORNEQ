import test from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import {readFileSync} from "node:fs";
const source=readFileSync(new URL("../assets/js/image-studio-gallery.js",import.meta.url),"utf8");
const id="8b5fbe11-8e1d-4de4-82b8-fac4f010c464";
const other="71c1d0c6-4b4c-41ad-90f7-510b8ecd1f81";
const row=id=>({id,status:"completed",size:"1024x1024",created_at:"2026-11-22T00:00:00Z"});
const flush=()=>new Promise(r=>setImmediate(r));
function boot({share, pages}={}){
 const nodes=new Map(),calls=[], observed=[];
 function node(){
  return {dataset:{},style:{},children:[],handlers:{},hidden:false,
   addEventListener(k,f){this.handlers[k]=f},fire(k,e={}){return this.handlers[k]?.(e)},
   append(...n){this.children.push(...n)},prepend(...n){this.children.unshift(...n)},
   setAttribute(k,v){this[k]=v},getAttribute(k){return this[k]},removeAttribute(k){delete this[k]},
   focus(){this.focused=true},showModal(){this.open=true},close(){this.open=false;this.fire("close")},
   querySelector(s){return get(this.scope ? this.scope + s : s)}};
 }
 function get(s){if(!nodes.has(s))nodes.set(s,node());return nodes.get(s)}
 const root=get("[data-vq-image-studio]"),gallery=get("[data-vq-gallery]");
 root.dataset.createUrl="/jobs/";gallery.dataset.historyUrl="/history/";
 get('[data-vq-toolbar="current"]').scope="current";get('[data-vq-toolbar="selected"]').scope="selected"; const list=pages||[{results:[row(id)],next_cursor:null,has_more:false}];
 let intersect;
 const navigator={share,canShare:()=>true};
 const window={isSecureContext:false,get localStorage(){throw Error("persistence")}};
 const context={document:{querySelector:get,createElement:node,getElementById:()=>({textContent:"{}"}),documentElement:{lang:"en"}},
 window,navigator,URL,AbortController,File:class {constructor(parts,name,options){this.name=name;this.type=options.type}},
 IntersectionObserver:class {constructor(f){intersect=f}observe(n){observed.push(n)}unobserve(){}},
 setTimeout:()=>1,clearTimeout:()=>{},
 fetch:async(url,opts)=>{calls.push({url,...opts});assert.equal(opts.method,"GET");
 if(url.startsWith("/history/"))return {status:200,json:async()=>list.shift()};
 if(url.endsWith("/download/"))return {status:200,blob:async()=>({type:"image/png",size:100})};
 return {status:200,json:async()=>({id:url.split("/")[2],status:"completed",image_url:"https://private.example.test/"+url.split("/")[2]})};}};
 vm.runInNewContext(source,context);
 return {get,root,calls,observed,intersect:()=>intersect(observed.map(target=>({target,isIntersecting:true})))};
}
test("history metadata only until thumbnail becomes visible",async()=>{
 const p=boot();await flush();assert.equal(p.calls.length,1);assert.equal(p.observed.length,1);
 p.intersect();await flush();assert.equal(p.calls.length,2);assert.equal(p.observed[0].children[0].src,"https://private.example.test/"+id);
});
test("pagination deduplicates records",async()=>{
 const p=boot({pages:[{results:[row(id)],next_cursor:"abc",has_more:true},{results:[row(id),row(other)],next_cursor:null,has_more:false}]});
 await flush();p.get("[data-vq-gallery-more]").fire("click");await flush();assert.equal(p.observed.length,2);assert.match(p.calls[1].url,/cursor=abc/);
});
test("history selection leaves current toolbar identity intact",async()=>{
 const p=boot({pages:[{results:[row(id)],next_cursor:null,has_more:false},{results:[row(other)],next_cursor:null,has_more:false}]});
 await flush();p.root.fire("vq-image:completed",{detail:{id:other}});await flush();
 p.observed[0].fire("click");await flush();
 assert.equal(p.get("[data-vq-gallery-selected-img]").src,"https://private.example.test/"+id);
 assert.equal(p.get('current[data-vq-tool="download"]').href,"/jobs/"+other+"/download/"); assert.equal(p.get('selected[data-vq-tool="download"]').href,"/jobs/"+id+"/download/");
 assert.ok(p.calls.every(c=>c.method==="GET"));
});
test("share cancellation does not issue a second download or POST",async()=>{
 let shared;const p=boot({share:async data=>{shared=data;throw Object.assign(Error(),{name:"AbortError"})}});
 await flush();p.observed[0].fire("click");await flush();await p.get('selected[data-vq-tool="share"]').fire("click");await flush();
 assert.equal(shared.files[0].name,"VORNEQ-image-"+id+".png");
 assert.equal(p.calls.filter(c=>c.url.endsWith("/download/")).length,1);
});
