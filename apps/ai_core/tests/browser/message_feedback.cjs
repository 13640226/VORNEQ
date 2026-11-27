/* Exercise the actual feedback controller with a minimal DOM and fake same-origin fetch. */
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm"),path=require("node:path");
const source=fs.readFileSync(path.resolve(__dirname,"../../../../assets/js/phase-c-chat.js"),"utf8");
const start=source.indexOf("    function addFeedback("),end=source.indexOf("    function focusAnswer(",start);
assert(start>=0&&end>start);
class Node {
 constructor(tag){this.tag=tag;this.children=[];this.attrs={};this.events={};this.disabled=false;this.isConnected=true;}
 appendChild(child){this.children.push(child);return child;}
 setAttribute(k,v){this.attrs[k]=v;}
 addEventListener(k,fn){this.events[k]=fn;}
}
const document={createElement:tag=>new Node(tag),createElementNS:(_,tag)=>new Node(tag)};
const window={location:{origin:"https://synthetic.invalid"},setTimeout,clearTimeout};
const root={dataset:{vqConvEndpoint:"/api/ai/v1/conversations/",vqFeedbackLike:"Like",vqFeedbackDislike:"Dislike",vqFeedbackError:"Failed"}};
const token={value:"synthetic-csrf"};
const conversation="00000000-0000-4000-8000-000000000001",message="00000000-0000-4000-8000-000000000002";
let serverRating=null,requests=[],failMutation=false,failRead=false,delayMutation=null;
async function fetch(url,options){
 requests.push([url,options.method,options.body]);
 assert.equal(url,"/api/ai/v1/conversations/"+conversation+"/messages/"+message+"/feedback/");
 assert.equal(options.credentials,"same-origin");
 assert.equal(options.cache,"no-store");
 assert.equal(options.redirect,"error");
 assert.equal(options.headers["X-CSRFToken"],token.value);
 if(options.method==="GET"&&failRead)return {ok:false};
 if(options.method==="POST")serverRating=JSON.parse(options.body).rating;
 if(options.method==="DELETE")serverRating=null;
 if(options.method!=="GET"&&delayMutation)await delayMutation;
 if(options.method!=="GET"&&failMutation)return {ok:false};
 return {ok:true,json:async()=>({rating:serverRating})};
}
const ctx=vm.createContext({document,window,root,token,URL,fetch,AbortController});
vm.runInContext(source.slice(start,end),ctx);
const flush=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 const invalid=new Node("article");ctx.addFeedback(invalid,conversation,"not-a-uuid",null);
 assert.equal(invalid.children.length,0);
 const bubble=new Node("article");ctx.addFeedback(bubble,conversation,message,null);
 const [up,down,note]=bubble.children[0].children;
 const pressed=b=>b.attrs["aria-pressed"]==="true";
 assert.equal(requests.length,0);assert.equal(up.disabled,false);assert.equal(pressed(up),false);
 let resolve;delayMutation=new Promise(r=>resolve=r);
 const click=up.events.click();assert.equal(up.disabled,true);assert.equal(pressed(up),false);
 await down.events.click();assert.equal(requests.length,1);
 resolve();await click;delayMutation=null;assert.equal(pressed(up),true);
 await down.events.click();assert.equal(pressed(up),false);assert.equal(pressed(down),true);
 await down.events.click();assert.equal(requests.at(-1)[1],"DELETE");assert.equal(pressed(down),false);
 failMutation=true;await up.events.click();
 assert.equal(note.textContent,"Failed");assert.equal(requests.at(-1)[1],"GET");
 assert.equal(pressed(up),true); // server committed, authoritative GET confirmed it
 failRead=true;await up.events.click();assert.equal(up.disabled,true);assert.equal(pressed(up),false);
 failMutation=false;failRead=false;
 const fresh=new Node("article");serverRating="dislike";ctx.addFeedback(fresh,conversation,message,undefined);
 assert.equal(fresh.children[0].children[0].disabled,true);
 await flush();assert.equal(pressed(fresh.children[0].children[1]),true);
 const before=requests.length;fresh.isConnected=false;await fresh.children[0].children[0].events.click();
 assert.equal(requests.length,before);
 const malicious=new Node("article");root.dataset.vqConvEndpoint="//evil.invalid/";
 ctx.addFeedback(malicious,conversation,message,null);assert.equal(malicious.children.length,0);
 console.log("FEEDBACK_UI_SERVER_CONFIRMED_PASS");
})().catch(error=>{console.error(error);process.exitCode=1;});
