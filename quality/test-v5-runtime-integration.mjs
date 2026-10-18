import assert from 'node:assert/strict';
import {observeAfterCleanup,attachV5TraceDiagnostics} from './v5-runtime-integration.mjs';
import {sanitizeAttemptDiagnostics,inspectLighthouseReport,runWithIntegrityRetries} from './lighthouse-integrity.mjs';
const valid=()=>({audits:{'largest-contentful-paint':{numericValue:1000},'cumulative-layout-shift':{numericValue:0.01}},categories:{performance:{score:0.9}}});
const trace={Trace:{traceEvents:[{name:'navigationStart',url:'SECRET',cookie:'SECRET'}]}};
const order=[];
const completed=await observeAfterCleanup(async()=>{order.push('lighthouse');try {return {lhr:valid(),runnerArtifacts:trace,attemptDiagnostics:{}};}finally{order.push('cleanup');}},()=>order.push('scan'));
assert.deepEqual(order,['lighthouse','cleanup','scan']);
assert.equal(completed.attemptDiagnostics.v5Trace.navigationStart,'event-name-observed');
assert.equal(typeof completed.attemptDiagnostics.v5Trace.scanElapsedMs,'number');
assert.equal(typeof completed.attemptDiagnostics.v5Trace.heapDeltaMiB,'number');
assert.ok(!('runnerArtifacts' in completed));
assert.ok(!JSON.stringify(sanitizeAttemptDiagnostics(completed.attemptDiagnostics)).includes('SECRET'));
for (const [lhr,artifacts,expected] of [
  [valid(),{},'unknown'],
  [{...valid(),runtimeError:{code:'NO_NAVSTART'}},trace,'event-name-observed'],
  [{...valid(),runtimeError:{code:'NO_NAVSTART'}},{},'unknown']
]) {
  const result=await observeAfterCleanup(async()=>({lhr,runnerArtifacts:artifacts,attemptDiagnostics:{}}));
  assert.equal(result.attemptDiagnostics.v5Trace.navigationStart,expected);
}
const huge={Trace:{traceEvents:Array.from({length:250001},()=>({name:'other'}))}};
assert.equal((await observeAfterCleanup(async()=>({lhr:valid(),runnerArtifacts:huge,attemptDiagnostics:{}}))).attemptDiagnostics.v5Trace.navigationStart,'unknown');
const bomb={};Object.defineProperty(bomb,'Trace',{get(){throw Error('SECRET')}});
assert.equal((await observeAfterCleanup(async()=>({lhr:valid(),runnerArtifacts:bomb,attemptDiagnostics:{}}))).attemptDiagnostics.v5Trace.navigationStart,'unknown');
let inspected=false;
await assert.rejects(observeAfterCleanup(async()=>{throw Error('cleanup failed');},()=>{inspected=true;}),/cleanup failed/);
assert.equal(inspected,false);
await assert.rejects(observeAfterCleanup(async()=>{throw Error('lighthouse rejected');}),/lighthouse rejected/);
await assert.rejects(observeAfterCleanup(async()=>{throw Error('timeout pending');}),/timeout pending/);
assert.equal(inspectLighthouseReport(valid()).status,'VALID');
assert.equal(inspectLighthouseReport({...valid(),runtimeError:{code:'NO_NAVSTART'}}).status,'MEASUREMENT_INVALID');
let calls=0;
const retry=await runWithIntegrityRetries({maxAttempts:2,executeAttempt:()=>observeAfterCleanup(async()=>{calls++;const lhr=calls===1?{...valid(),runtimeError:{code:'NO_NAVSTART'}}:valid();return {lhr,runnerArtifacts:{},attemptDiagnostics:{}};})});
assert.equal(calls,2);assert.equal(retry.attempts,2);assert.equal(retry.status,'VALID');
let failed=0;await assert.rejects(runWithIntegrityRetries({maxAttempts:2,isRecoverableError:()=>true,executeAttempt:()=>observeAfterCleanup(async()=>{failed++;throw Error('reject');})}));assert.equal(failed,2);
const v5=sanitizeAttemptDiagnostics(attachV5TraceDiagnostics({},trace));
assert.equal(v5.v5Trace.traceKey,'Trace');
assert.ok(v5.v5Trace.scanElapsedMs>=0);
console.log('PASS post-cleanup mock ordering, rejection, timeout, NO_NAVSTART, retry, bounded scan, overhead, redaction');
