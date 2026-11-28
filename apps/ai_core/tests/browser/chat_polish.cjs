const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict"),path=require("node:path");
const src=fs.readFileSync(path.resolve(__dirname,"../../../../assets/js/phase-c-chat.js"),"utf8");
const start=src.indexOf("      function historyBucket("),end=src.indexOf("      function renderList(",start);
assert(start>=0&&end>start);
const ctx=vm.createContext({Date,Number});
vm.runInContext(src.slice(start,end),ctx);
const now=new Date(2026,10,27,0,10);
const stamp=(days,h=23)=>new Date(2026,10,27-days,h,50).toISOString();
for(const [v,expected] of [[stamp(0,0),"today"],[stamp(1),"yesterday"],[stamp(2),"week"],[stamp(7),"week"],[stamp(8),"older"],[stamp(-1),"unknown"],["invalid","unknown"],[null,"unknown"]])assert.equal(ctx.historyBucket(v,now),expected);
const a=src.indexOf("    function resizeComposer()"),b=src.indexOf("    function appendMessage",a);
assert(a>=0&&b>a);
let quiet=false;
const input={style:{},scrollHeight:108,value:"",disabled:false},count={textContent:"",classList:{toggle:(key,flag)=>{assert.equal(key,"vq-chat__count--quiet");quiet=flag}}},send={},clear={};
const state=vm.createContext({input,count,send,clear,byteLimit:8192,limit:8192,historyOnly:false,busy:false,recoveryBlocked:false,root:{classList:{toggle(){}}},inputCount:v=>Buffer.byteLength(v,"utf8"),fitsQuestion:v=>Buffer.byteLength(v,"utf8")<=8192});
vm.runInContext(src.slice(a,b),state);
for(const [value,expectedQuiet,expectedDisabled,display] of [["",true,true,"0/8192 B"],["a".repeat(7372),true,false,"7372/8192 B"],["a".repeat(7373),false,false,"7373/8192 B"],["آ".repeat(4097),false,true,"8194/8192 B"]]){
 input.value=value;state.update();assert.equal(quiet,expectedQuiet);assert.equal(send.disabled,expectedDisabled);assert.equal(count.textContent,display);assert.equal(input.style.height,"108px");
}
state.historyOnly=true;
input.value="a valid question";
state.update();
assert.equal(send.disabled,true);
assert.equal(input.disabled,true);
assert.equal(clear.disabled,true);
// Invoke the actual submit handler with history-only set, not just disabled HTML.
const first=src.indexOf('form.addEventListener("submit", async (event) => {');
const last=src.indexOf('    clear.addEventListener("click"',first);
assert(first>=0&&last>first);
let handler,prevented=false;
const guard=vm.createContext({historyOnly:true,busy:false,recoveryBlocked:false,
 form:{addEventListener:(name,fn)=>{assert.equal(name,"submit");handler=fn;}},
 input:{get value(){throw Error("history mode must not read or submit input");}},
 fetch(){throw Error("history mode must not fetch");}});
vm.runInContext(src.slice(first,last),guard);
(async()=>{await handler({preventDefault(){prevented=true;}});
assert.equal(prevented,true);
console.log("CHAT_POLISH_HISTORY_AND_COMPOSER_PASS");
console.log("HISTORY_ONLY_SUBMISSION_BLOCKED");
})().catch(e=>{console.error(e);process.exitCode=1;});
