// Optional diagnostic artifacts must never affect Lighthouse result or cleanup.
export function safelyReadRunnerArtifacts(runner) {
  try { return runner?.artifacts; }
  catch { return undefined; }
}
