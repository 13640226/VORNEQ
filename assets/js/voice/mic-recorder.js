(function(global) {
"use strict";
const MAX_BYTES=8*1024*1024,MAX_MS=120000;
class MicRecorder {
 constructor(cb={}) {this.cb=cb;this.state="idle";this.gen=0;this.chunks=[];this.bytes=0;this.discard=false;this.stream=null;this.rec=null;this.timer=null;}
 stateTo(s,reason){this.state=s;this.cb.onState?.(s,reason);}
 cleanup(){clearTimeout(this.timer);this.timer=null;this.stream?.getTracks().forEach(t=>t.stop());this.stream=null;}
 async start(){
  if(this.state!=="idle")return;
  if(!global.MediaRecorder||!navigator.mediaDevices?.getUserMedia){this.stateTo("error","unsupported_browser");return;}
  const gen=++this.gen;this.stateTo("starting");
  try{
   const stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
   if(gen!==this.gen){stream.getTracks().forEach(t=>t.stop());return;}
   this.stream=stream;
   const mime=["audio/webm;codecs=opus","audio/webm","audio/mp4","audio/ogg;codecs=opus","audio/ogg"].find(t=>MediaRecorder.isTypeSupported(t));
   const rec=this.rec=mime?new MediaRecorder(stream,{mimeType:mime}):new MediaRecorder(stream);
   this.discard=false;this.chunks=[];this.bytes=0;
   rec.ondataavailable=e=>{if(this.discard||!e.data?.size)return;this.bytes+=e.data.size;if(this.bytes>MAX_BYTES){this.cancel("limit_exceeded");return;}this.chunks.push(e.data);};
   rec.onerror=()=>this.cancel("recorder_error");
   rec.onstop=()=>{const deliver=!this.discard&&this.state==="stopping";const blob=deliver?new Blob(this.chunks,{type:rec.mimeType}):null;this.chunks=[];this.cleanup();this.rec=null;if(deliver){this.stateTo("idle");if(blob.size)this.cb.onStop?.(blob);}else if(this.state!=="error")this.stateTo("idle");};
   rec.start(1000);this.stateTo("recording");this.timer=setTimeout(()=>this.cancel("limit_exceeded"),MAX_MS);
  }catch(e){if(gen!==this.gen)return;this.discard=true;this.chunks=[];this.cleanup();this.rec=null;this.stateTo("error",e?.name==="NotAllowedError"?"permission_denied":e?.name==="NotFoundError"?"no_microphone":"recorder_error");}
 }
 stop(){if(this.state!=="recording")return;this.stateTo("stopping");clearTimeout(this.timer);try{this.rec.stop();}catch(e){this.cancel("recorder_error");}}
 cancel(reason){++this.gen;this.discard=true;this.chunks=[];this.bytes=0;const rec=this.rec;this.cleanup();this.stateTo(reason?"error":"idle",reason);if(rec&&rec.state!=="inactive"){try{rec.stop();}catch(e){}}}
 dispose(){this.cancel();}
}
global.VorneqMicRecorder=MicRecorder;
})(window);