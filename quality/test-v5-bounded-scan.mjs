import assert from 'node:assert/strict';
import {inspectExistingNavigationTrace as inspect} from './v5-navigation-trace.mjs';
import {observeAfterCleanup} from './v5-runtime-integration.mjs';
const trace = events => ({Trace:{traceEvents:events}});
const ev = name => ({name});
const clock = (sequence) => {let i=0;return () => sequence[Math.min(i++,sequence.length-1)];};
assert.equal(inspect(trace([ev('navigationStart')])).navigationStart,'event-name-observed');
assert.equal(inspect(trace([ev('other')])).navigationStart,'event-name-not-observed-in-available-trace');
let result=inspect(trace(Array.from({length:250001},()=>ev('other'))));
assert.equal(result.scannedEventCount,250000);
assert.equal(result.scanComplete,false);
assert.equal(result.navigationStart,'unknown');
result=inspect(trace(Array.from({length:1000},()=>ev('other'))),{
  now:clock([0,0,0,251]),heapUsed:()=>0
});
assert.equal(result.navigationStart,'unknown');
assert.equal(result.scanComplete,false);
assert.ok(result.scannedEventCount<=256);
result=inspect(trace(Array.from({length:1000},()=>ev('other'))),{
  now:()=>0,heapUsed:clock([0,0,0,33*1048576])
});
assert.equal(result.navigationStart,'unknown');
assert.equal(result.scanComplete,false);
result=inspect(trace([ev('navigationStart')]),{now:()=>{throw Error('clock')}});
assert.equal(result.navigationStart,'unknown');
result=inspect(trace([ev('navigationStart')]),{heapUsed:()=>NaN});
assert.equal(result.navigationStart,'unknown');
result=inspect({get Trace(){throw Error('getter')}});
assert.equal(result.navigationStart,'unknown');
assert.equal(inspect(null).navigationStart,'unknown');
assert.equal(inspect({Trace:{traceEvents:{}}}).navigationStart,'unknown');
const order=[];
const completed=await observeAfterCleanup(async()=>{
  order.push('lighthouse','cleanup');
  return {lhr:{audits:{}},attemptDiagnostics:{},runnerArtifacts:trace([ev('navigationStart')])};
},()=>order.push('scan'));
assert.deepEqual(order,['lighthouse','cleanup','scan']);
assert.equal(completed.attemptDiagnostics.v5Trace.navigationStart,'event-name-observed');
assert.equal('runnerArtifacts' in completed,false);
const hostile=await observeAfterCleanup(async()=>({
  lhr:{audits:{},valid:true},attemptDiagnostics:{},
  runnerArtifacts:{get Trace(){throw Error('secret-token-url-cookie')}}
}));
assert.equal(hostile.lhr.valid,true);
assert.equal(hostile.attemptDiagnostics.v5Trace.navigationStart,'unknown');
assert.equal(JSON.stringify(hostile).includes('secret-token-url-cookie'),false);
console.log('PASS bounded budgets, trace completeness, reader failure, cleanup ordering, safe degradation, sanitization');
