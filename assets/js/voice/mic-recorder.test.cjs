const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const src=fs.readFileSync(__dirname+"/mic-recorder.js","utf8");
function setup(error){
 let tracks=0,stops=0,delivered=0,permission=0;
 const track={stop(){tracks++}};
 class MediaRecorder{
  static isTypeSupported(){return true;}
  constructor(){this.state="inactive";this.mimeType="audio/webm";}
  start(){this.state="recording";}
  stop(){this.state="inactive";this.ondataavailable?.({data:new Blob(["hello"])});this.onstop?.();stops++;}
 }
 const window={MediaRecorder},navigator={mediaDevices:{async getUserMedia(){permission++;if(error)throw {name:error};return {getTracks:()=>[track]};}}};
 const context={window,navigator,MediaRecorder,Blob,setTimeout,clearTimeout};
 vm.runInNewContext(src,context);
 const recorder=new window.VorneqMicRecorder({onStop(){delivered++;}});
 return {recorder,counts:()=>({tracks,stops,delivered,permission})};
}
(async()=>{
 let x=setup();await x.recorder.start();assert.equal(x.recorder.state,"recording");await x.recorder.start();assert.equal(x.counts().permission,1);x.recorder.stop();assert.equal(x.counts().delivered,1);assert.equal(x.counts().tracks,1);
 x=setup();await x.recorder.start();x.recorder.cancel();assert.equal(x.counts().delivered,0);assert.equal(x.counts().tracks,1);
 x=setup("NotAllowedError");await x.recorder.start();assert.equal(x.recorder.state,"error");
 x=setup("NotFoundError");await x.recorder.start();assert.equal(x.recorder.state,"error");
 x=setup();await x.recorder.start();x.recorder.cancel("limit_exceeded");assert.equal(x.counts().delivered,0);assert.equal(x.recorder.state,"error");
 console.log("PASS: start, concurrent start, stop, cancel, permission, missing device, limit");
})().catch(e=>{console.error(e);process.exitCode=1;});