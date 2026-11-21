/* Actual browser DOM, production chat script, synthetic response only. */
"use strict";
window.addEventListener("DOMContentLoaded", async () => {
  const form = document.querySelector("[data-vq-chat-form]");
  const log = document.querySelector("[data-vq-chat-log]");
  const input = document.querySelector("[data-vq-chat-input]");
  const output = document.getElementById("results");
  const clear = document.querySelector("[data-vq-chat-clear]");
  const tick = () => new Promise(resolve => setTimeout(resolve, 20));
  let count = 0;
  let calls = 0;
  let responseBody;
  const response = answer => ({mode:"grounded_draft", verified:false, answer, citations:[]});
  window.fetch = async (_url, options) => {
    if (options.method !== "POST") throw new Error("unexpected fetch");
    calls++;
    return {ok:true, status:200, json:async () => responseBody};
  };
  function check(condition, label) {
    if (!condition) throw new Error(label);
    count++;
    output.textContent += "PASS " + label + "\n";
  }
  async function render(answer) {
    clear.click();
    responseBody = typeof answer === "string" ? response(answer) : answer;
    input.value = "offline synthetic prompt";
    form.dispatchEvent(new Event("submit", {bubbles:true, cancelable:true}));
    for (let i=0;i<30 && !log.querySelector(".vq-chat__rich");i++) await tick();
    const node = log.querySelector(".vq-chat__rich");
    if (!node) throw new Error("rich response did not render");
    return node;
  }
  try {
    const payloads = [
      "<script>window.__injected=1</script>",
      "<img src=x onerror=window.__injected=1>",
      "[click](javascript:window.__injected=1)",
      "<svg onload=window.__injected=1><a href=javascript:alert(1)>x</a></svg>",
      "**<iframe src=javascript:alert(1)>**",
      "\x60<img src=x onerror=alert(1)>\x60"
    ];
    for (const payload of payloads) {
      const node = await render(payload);
      check(!node.querySelector("script,img,svg,iframe,object,embed,a,[onload],[onerror],[href],[src]"), "no executable DOM: " + payload);
      check(node.textContent.includes(payload.replace(/^\*\*|\*\*$|^\x60|\x60$/g,"")), "payload remains literal text");
    }
    check(window.__injected === undefined, "no payload execution");
    const fence = "\x60".repeat(3);
    let node = await render(fence + "python\nprint('<script>')\n" + fence);
    check(node.querySelector("pre code").textContent === "print('<script>')", "fenced code text exact");
    node = await render(fence+"js\n<script>unfinished");
    check(!node.querySelector("pre,script") && node.textContent.includes(fence+"js\n<script>unfinished"), "unclosed fence literal fallback");
    node = await render("| name | value |\n| --- | --- |\n| alpha | **beta** |");
    check(node.querySelectorAll("table th").length===2 && node.querySelector("td strong").textContent==="beta", "table header and bold DOM");
    const wide = "|" + "x|".repeat(13) + "\n|" + "---|".repeat(13);
    node = await render(wide);
    check(!node.querySelector("table") && node.textContent.includes(wide.split("\n")[0]), "oversized table columns literal");
    const tall = "| a |\n| --- |\n" + "| x |\n".repeat(101);
    node = await render(tall);
    check(!node.querySelector("table") && node.textContent.includes("| x |"), "oversized table rows literal");
    const multiline = "x\n".repeat(257);
    node = await render(multiline);
    check(node.querySelectorAll("p").length===1 && node.textContent===multiline, "DOM line budget literal");
    const mixed = "\u0641\u0627\u0631\u0633\u06cc English \u00fc";
    node = await render(mixed+"\n"+fence+"\n"+mixed+"\n"+fence);
    check(node.dir==="auto" && node.querySelector("pre").dir==="ltr" && node.querySelector("code").textContent===mixed, "RTL/LTR and unicode code preservation");
    node = await render({...response("Long section"),format_version:2,sections:[{kind:"answer",heading:"Title",text:"**Section**",refs:["S1.P1"]}]});
    check(node.querySelector("strong").textContent==="Section" && log.querySelector(".vq-chat__section-refs").textContent==="S1.P1","section path and reference rendering");
    for (const count of [8, 9, 24, 25]) {
      const citations = [];
      let remaining = count;
      for (let n=1; n<=3 && remaining; n++) {
        const size = Math.min(9, remaining);
        citations.push({source_id:"S"+n,title:"Synthetic source",passages:
          Array.from({length:size},(_,i)=>({passage_id:"S"+n+".P"+(i+1),quote:"x".repeat(80),section_indices:[Math.floor(i/4)]}))});
        remaining -= size;
      }
      await render({...response("Synthetic answer"),format_version:2,citations});
      check(log.querySelectorAll(".vq-chat__passages li").length === (count<=24 ? count : 0),
        "passage aggregate bound: "+count);
    }
    check(calls===18, "exactly one synthetic POST per response");
    document.body.dataset.result="PASS";
    output.textContent += "PASS_COUNT="+count;
  } catch(error) {
    document.body.dataset.result="FAIL";
    output.textContent += "FAIL "+error.message;
  }
});
