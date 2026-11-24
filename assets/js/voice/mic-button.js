(function(){
"use strict";
function boot(){
 const form=document.querySelector("[data-vq-chat-form]"),send=form?.querySelector("[data-vq-chat-send]");
 if(!send||form.querySelector("[data-vq-mic-button]")||!window.VorneqMicRecorder)return;
 const lang=(document.querySelector("[data-vq-chat]")?.dataset.vqLanguage||document.documentElement.lang||"en").slice(0,2);
 const labels={fa:["شروع ضبط صدا","توقف ضبط صدا","لغو ضبط"],de:["Aufnahme starten","Aufnahme stoppen","Aufnahme verwerfen"],en:["Start recording","Stop recording","Discard recording"]}[lang]||["Start recording","Stop recording","Discard recording"];
 const mic=document.createElement("button"),cancel=document.createElement("button");
 mic.type=cancel.type="button";mic.className="vq-voice-mic";cancel.className="vq-voice-cancel";mic.dataset.vqMicButton="1";mic.textContent="🎙";cancel.textContent="×";cancel.hidden=true;
 const recorder=new window.VorneqMicRecorder({onState(state){mic.dataset.state=state;const brand=document.querySelector("[data-vq-ai-brand]");if(brand&&form.getAttribute("aria-busy")!=="true")brand.dataset.state=state==="error"?"error":state==="starting"||state==="stopping"?"thinking":"idle";mic.setAttribute("aria-label",state==="recording"?labels[1]:labels[0]);mic.setAttribute("aria-pressed",String(state==="recording"));mic.disabled=state==="starting"||state==="stopping";cancel.hidden=state!=="recording"&&state!=="starting";},onStop(_blob){/* intentionally discarded; no network or storage */}});
 mic.setAttribute("aria-label",labels[0]);mic.setAttribute("aria-pressed","false");cancel.setAttribute("aria-label",labels[2]);
 send.before(mic,cancel);
 mic.addEventListener("click",()=>{if(recorder.state==="recording")recorder.stop();else if(recorder.state==="idle")recorder.start();else if(recorder.state==="error"){recorder.stateTo("idle");recorder.start();}});
 cancel.addEventListener("click",()=>recorder.cancel());
 window.addEventListener("pagehide",()=>recorder.dispose());
 document.addEventListener("visibilitychange",()=>{if(document.hidden)recorder.dispose();});
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot);else boot();
})();