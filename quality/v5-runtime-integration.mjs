import { performance } from 'node:perf_hooks';
import { inspectExistingNavigationTrace } from './v5-navigation-trace.mjs';
const unknown = () => ({source:'lighthouse-12.8.2-runner-artifacts',traceAccess:'unavailable',traceKey:null,navigationStart:'unknown',matchingEventCount:null,scannedEventCount:0,scanComplete:false});
export function attachV5TraceDiagnostics(evidence, artifacts) {
  const started=performance.now();
  const heapBefore=process.memoryUsage().heapUsed;
  let result;
  try { result=inspectExistingNavigationTrace(artifacts); }
  catch { result=unknown(); }
  let elapsed=null, delta=null;
  try {
    const ms=performance.now()-started;
    const mib=(process.memoryUsage().heapUsed-heapBefore)/1048576;
    elapsed=Number.isFinite(ms)&&ms>=0&&ms<=180000?Math.round(ms*10)/10:null;
    delta=Number.isFinite(mib)&&Math.abs(mib)<=100000?Math.round(mib*100)/100:null;
  } catch { /* telemetry must never affect measurement */ }
  evidence.v5Trace={...result,scanElapsedMs:elapsed,heapDeltaMiB:delta};
  return evidence;
}
export async function observeAfterCleanup(runCore, onObserved=()=>{}) {
  const completed=await runCore(); // runCore resolves only after its finally cleanup
  try { attachV5TraceDiagnostics(completed.attemptDiagnostics, completed.runnerArtifacts); onObserved(); }
  catch { /* best effort, never change result or retry */ }
  const {runnerArtifacts, ...original}=completed;
  return original;
}
