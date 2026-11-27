const fs=require("node:fs");
const vm=require("node:vm");
const assert=require("node:assert/strict");
const path=require("node:path");
// Run the real setUrl implementation in an isolated browser-like context.
// No network or provider requests. Run with node from any working directory.
const src=fs.readFileSync(path.resolve(__dirname,"../../../../assets/js/phase-c-chat.js"),"utf8");
const start=src.indexOf("      function setUrl(id) {");
const end=src.indexOf("      function showBar",start);
assert(start>=0&&end>start,"setUrl function must be present");
const first="11111111-2222-4333-8444-555555555555";
const second="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
const origin="https://local.invalid";
const base="/api/ai/v1/chat/";
const languages=["fa","de","en"];
const fields=languages.map(lang=>({value:base+"?lang="+lang+"&c="+first}));
const external={value:"https://example.invalid"+base+"?lang=fa"};
const wrongPath={value:"/other/?lang=fa"};
const state={
  URL,
  uuidPattern:/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
  window:{location:{href:origin+base+"?lang=de&c="+first,origin},
    history:{replaceState(_a,_b,p){state.window.location.href=origin+p;}}},
  document:{querySelectorAll(selector){
    assert.equal(selector,"[data-vq-chat-language-next]");
    return [...fields,external,wrongPath];
  }}
};
vm.createContext(state);
vm.runInContext(src.slice(start,end),state);
state.setUrl(second);
fields.forEach((f,i)=>{
  const u=new URL(f.value,origin);
  assert.equal(u.searchParams.get("c"),second);
  assert.equal(u.searchParams.get("lang"),languages[i]);
});
state.setUrl(null);
fields.forEach(f=>assert.equal(new URL(f.value,origin).searchParams.has("c"),false));
assert.equal(external.value,"https://example.invalid"+base+"?lang=fa");
assert.equal(wrongPath.value,"/other/?lang=fa");
console.log("LANGUAGE_CONVERSATION_SYNC_PASS");
