'use strict';
// VORNEQ V2 isolated, offline-only Node built-in conformance tests.
// Deliberately independent of Python Golden/implementation, V1 or filesystem IO.
const test = require('node:test');
const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const v2 = require('../config/offline_admin_canonical_independent_verifier_v2.js');

const REFERENCE = Buffer.from(String.raw`{"anchor":{"files":[{"origin":"git-tracked","path":"config/__init__.py","sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},{"origin":"isolated-untracked","path":"config/isolated_admin_test_guard.py","sha256":"e935f1e6bc95ab8225fda8676e1d56fa25acfb555c2fa85c1e850fac9994d21b"},{"origin":"isolated-untracked","path":"config/settings_isolated_admin_test.py","sha256":"d8b6ed2f5240254e2361cc288b356c1de3afc5117602d6d8863c19dec6ee5e58"},{"origin":"isolated-untracked","path":"config/urls_isolated_admin_test.py","sha256":"a4629e61a85508b29d0e7e7f493aaf45634717aeceea3c801610d32c0b361251"},{"origin":"git-tracked","path":"marketplace/__init__.py","sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},{"origin":"git-tracked-modified","path":"marketplace/admin.py","sha256":"35b31f0c9a0f4e5830283e3c936df113cde4581ef725ea4c15b8eb48e626cab4"},{"origin":"git-tracked","path":"marketplace/models.py","sha256":"d7fb9dd3ce8fa803bf594a3dbac0e94edd26ec0e45fad25a22376b3a6a95f2bb"},{"origin":"isolated-untracked","path":"marketplace/test_admin_moderation_invariants_offline.py","sha256":"1ff33927e0c62f3831a2fb92c33cfc8fb70d7521558cb11b7aa0e8c4bd98d476"},{"origin":"isolated-untracked","path":"marketplace/test_isolated_admin_settings_static.py","sha256":"a92e2ca21b0ac5be6035c8af602288729ce41cba1e715e3f99d350bf2a56fc4c"}],"project":"13640226/VORNEQ","purpose":"OFFLINE_ADMIN_STATIC_TESTS_ONLY","schema":"VORNEQ_OFFLINE_ADMIN_TRUST_ANCHOR_V1","source_head":"f64bb717e4dfddcc3832d5f9c7c9f6b998732983","validator":{"path":"config/offline_admin_package_manifest_validator.py","sha256":"08bc25bb1a417073267ea316ec9e8f7a83591f2679df434051692edad892773d"},"worktree_exception":{"path":"marketplace/admin.py","sha256":"35b31f0c9a0f4e5830283e3c936df113cde4581ef725ea4c15b8eb48e626cab4"}},"canonicalization_version":"VORNEQ_JSON_ASCII_SORTED_COMPACT_SAFEINT_V2","digest_algorithm":"SHA-256","environment_id":"SIMULATED_ENVIRONMENT_ONLY","evidence_class":"SIMULATED","expires_at":"2026-10-16T00:00:00Z","issued_at":"2026-10-15T00:00:00Z","monotonic_version":1,"nonce":"0123456789abcdef0123456789abcdef","project_id":"13640226/VORNEQ","purpose":"OFFLINE_ADMIN_STATIC_TESTS_ONLY","schema":"VORNEQ_OFFLINE_ADMIN_CANONICAL_CONTRACT_V2","simulation_only":true,"snapshot_id":"SIMULATED_SNAPSHOT_ONLY","source_head":"f64bb717e4dfddcc3832d5f9c7c9f6b998732983","source_repository_id":"13640226/VORNEQ"}`, 'ascii');
const DOMAIN = 'VORNEQ:OFFLINE_ADMIN_STATIC_CANONICAL_V2\0';
const BASE_RAW_SHA = 'eec0ab9f4170c680ed0f24602238c2b47d005cc01e3b735ef454832f99a72b2a';
const BASE_DOMAIN_SHA = '40c822761ddfda09df74e1aba460e23aea294502e6ce4269207e12d9c007a44f';
const MAX_RAW_SHA = '9da5b10eee472c0459304e78c658225bfa180a4c830c150f370a83cdefe5f54c';
const MAX_DOMAIN_SHA = '17c8364932d812d338e12081873bebf96e6b5df63f422b56aa57a97e40596650';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const separated = (domain, bytes) =>
  createHash('sha256').update(domain,'ascii').update(bytes).digest('hex');
const str = () => REFERENCE.toString('ascii');

function mutate(oldPart, newPart) {
  const s = str();
  const idx = s.indexOf(oldPart);
  if (idx < 0 || s.indexOf(oldPart, idx + oldPart.length) >= 0)
    throw new Error('Fixture mutation must have exactly one source span');
  return Buffer.from(s.slice(0, idx) + newPart +
                     s.slice(idx + oldPart.length), 'ascii');
}
function mutateBytes(oldPart, newPart) {
  const pattern = Buffer.from(oldPart,'ascii');
  const idx = REFERENCE.indexOf(pattern);
  if (idx < 0 || REFERENCE.indexOf(pattern,idx+1) >= 0)
    throw new Error('Ambiguous byte fixture recipe');
  return Buffer.concat([REFERENCE.subarray(0,idx),newPart,
    REFERENCE.subarray(idx+pattern.length)]);
}
const MAX_REFERENCE = mutate('"monotonic_version":1,',
  '"monotonic_version":9007199254740991,');
const cases = [];
function add(id, bytes, accept=false) {
  cases.push(Object.freeze({id,bytes,accept}));
}
add('V2-01', REFERENCE, true);
add('V2-02', MAX_REFERENCE, true);
add('V2-03', mutate('"monotonic_version":1,','"monotonic_version":0,'));
add('V2-04', mutate('"monotonic_version":1,','"monotonic_version":-1,'));
add('V2-05', mutate('"monotonic_version":1,','"monotonic_version":9007199254740992,'));
add('V2-06', mutate('"monotonic_version":1,','"monotonic_version":9007199254740993,'));
add('V2-07', mutate('"monotonic_version":1,','"monotonic_version":1.0,'));
add('V2-08', mutate('"monotonic_version":1,','"monotonic_version":1e0,'));
add('V2-09', mutate('"monotonic_version":1,','"monotonic_version":true,'));
add('V2-10', mutate('"monotonic_version":1,','"monotonic_version":01,'));
add('V2-11', mutate('"schema":"VORNEQ_OFFLINE_ADMIN_CANONICAL_CONTRACT_V2",',
  '"schema":"VORNEQ_OFFLINE_ADMIN_CANONICAL_CONTRACT_V2","schema":"VORNEQ_OFFLINE_ADMIN_CANONICAL_CONTRACT_V2",'));
add('V2-12', mutate('"validator":{"path":"config/offline_admin_package_manifest_validator.py",',
  '"validator":{"path":"config/offline_admin_package_manifest_validator.py","path":"config/offline_admin_package_manifest_validator.py",'));
add('V2-13', mutate('"digest_algorithm":"SHA-256","environment_id":"SIMULATED_ENVIRONMENT_ONLY",',
  '"environment_id":"SIMULATED_ENVIRONMENT_ONLY","digest_algorithm":"SHA-256",'));
add('V2-14', mutate('"nonce":"0123456789abcdef',
  '"nonce":"\\u0030123456789abcdef'));
add('V2-15', mutateBytes('"project_id":"13640226/VORNEQ"',
  Buffer.concat([Buffer.from('"project_id":"13640226/','ascii'),
    Buffer.from([0xc3,0xa9]),Buffer.from('ORNEQ"','ascii')])));
add('V2-16', Buffer.concat([Buffer.from([0xef,0xbb,0xbf]),REFERENCE]));
add('V2-17', Buffer.concat([Buffer.from(' '),REFERENCE]));
add('V2-18', mutate('"issued_at":"2026-10-15T00:00:00Z"',
  '"issued_at":"2026-02-30T00:00:00Z"'));
add('V2-19', mutate('"expires_at":"2026-10-16T00:00:00Z"',
  '"expires_at":"2026-10-15T00:00:00Z"'));
add('V2-20', mutate('"issued_at":"2026-10-15T00:00:00Z"',
  '"issued_at":"2026-10-01T00:00:00Z"'));

add('V2-21', mutate("{\"origin\":\"git-tracked\",\"path\":\"config/__init__.py\",\"sha256\":\"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\"},{\"origin\":\"isolated-untracked\",\"path\":\"config/isolated_admin_test_guard.py\",\"sha256\":\"e935f1e6bc95ab8225fda8676e1d56fa25acfb555c2fa85c1e850fac9994d21b\"}",
  "{\"origin\":\"isolated-untracked\",\"path\":\"config/isolated_admin_test_guard.py\",\"sha256\":\"e935f1e6bc95ab8225fda8676e1d56fa25acfb555c2fa85c1e850fac9994d21b\"},{\"origin\":\"git-tracked\",\"path\":\"config/__init__.py\",\"sha256\":\"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\"}"));
add('V2-22', mutate("{\"origin\":\"git-tracked\",\"path\":\"config/__init__.py\",\"sha256\":\"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\"}",
  "{\"origin\":\"git-tracked\",\"path\":\"config/__init__.py\",\"sha256\":\"0000000000000000000000000000000000000000000000000000000000000000\"}"));
add('V2-23', mutate('"schema":"VORNEQ_OFFLINE_ADMIN_TRUST_ANCHOR_V1"',
  '"schema":"VORNEQ_OFFLINE_ADMIN_TRUST_ANCHOR_V2"'));
add('V2-24', mutate('"schema":"VORNEQ_OFFLINE_ADMIN_CANONICAL_CONTRACT_V2"',
  '"schema":"VORNEQ_OFFLINE_ADMIN_CANONICAL_CONTRACT_V1"'));
add('V2-25', mutate('"canonicalization_version":"VORNEQ_JSON_ASCII_SORTED_COMPACT_SAFEINT_V2"',
  '"canonicalization_version":"PYTHON_JSON_ASCII_SORTED_COMPACT_V1"'));
add('V2-26', Buffer.alloc(32769,0x20));
add('V2-27', Buffer.from('['.repeat(33)+'0'+']'.repeat(33),'ascii'));
add('V2-28', mutate('"monotonic_version":1,',
  '"monotonic_version":'+'9'.repeat(40)+','));
add('V2-29', mutate('"nonce":"0123456789abcdef0123456789abcdef"',
  '"nonce":"0123456789abcdef0123456789abcdeg"'));
add('V2-30', mutate('"issued_at":"2026-10-15T00:00:00Z"',
  '"issued_at":"2026-10-15T01:00:00+01:00"'));

function fixtureEvidence() {
  const checks = Object.create(null);
  for (const key of [
    'independent_reference_available','signature_or_owner_reference_reviewed',
    'source_git_provenance_checked','snapshot_membership_checked',
    'snapshot_bytes_checked','snapshot_write_protection_checked',
    'network_isolation_checked','secrets_isolation_checked',
  ]) checks[key] = true;
  return {
    schema:'VORNEQ_OFFLINE_ADMIN_CANONICAL_SIMULATION_EVIDENCE_V2',
    evidence_class:'SIMULATED',simulation_only:true,
    source:'IN_MEMORY_FIXTURE',requested_stage:'STATIC_CONTRACT_CHECK_ONLY',
    contract_sha256:BASE_DOMAIN_SHA,hypothetical_checks:checks,
    external_trust_authenticated:false,signature_verified:false,
    os_measurements_verified:false,snapshot_verified:false,
    runtime_authorized:false
  };
}
const time = '2026-10-15T12:00:00Z';

test('CIV-01 pinned independent bytes and both SHA256 modes',()=>{
  assert.equal(REFERENCE.length,2418);
  assert.equal(sha(REFERENCE),BASE_RAW_SHA);
  assert.equal(separated(DOMAIN,REFERENCE),BASE_DOMAIN_SHA);
  assert.equal(MAX_REFERENCE.length,2433);
  assert.equal(sha(MAX_REFERENCE),MAX_RAW_SHA);
  assert.equal(separated(DOMAIN,MAX_REFERENCE),MAX_DOMAIN_SHA);
});
test('CIV-02 expected 30 unique cases and valid suite metadata',()=>{
  assert.equal(cases.length,30);
  assert.equal(new Set(cases.map(x=>x.id)).size,30);
  assert.equal(v2.SCHEMA,'VORNEQ_OFFLINE_ADMIN_CANONICAL_CONTRACT_V2');
  assert.equal(v2.PROFILE,'VORNEQ_JSON_ASCII_SORTED_COMPACT_SAFEINT_V2');
  assert.equal(v2.MAX_DEPTH,32);
  assert.equal(v2.MAX_NUMBER_TOKEN,20);
});
test('CIV-03 baseline bytes and hashes via independent JS verifier',()=>{
  const parsed=v2.parseRaw(REFERENCE);
  assert.deepEqual(v2.canonicalizeObject(parsed),REFERENCE);
  const r=v2.inspect(REFERENCE);
  assert.equal(r.result,'STATIC_CANONICAL_SCHEMA_VALID');
  assert.equal(r.raw,BASE_RAW_SHA);
  assert.equal(r.domain,BASE_DOMAIN_SHA);
  assert.equal(r.runtime_authorized,false);
});
test('CIV-04 max version bytes and hashes via JS verifier',()=>{
  const parsed=v2.parseRaw(MAX_REFERENCE);
  assert.equal(parsed.monotonic_version,9007199254740991);
  assert.deepEqual(v2.canonicalizeObject(parsed),MAX_REFERENCE);
  const r=v2.inspect(MAX_REFERENCE);
  assert.equal(r.raw,MAX_RAW_SHA);
  assert.equal(r.domain,MAX_DOMAIN_SHA);
});
for(const c of cases) {
  test('CANONICAL '+c.id+' '+(c.accept?'accept':'reject'),()=>{
    if(c.accept) {
      const r=v2.inspect(c.bytes);
      assert.equal(r.authenticated,false);
      assert.deepEqual(v2.canonicalizeObject(v2.parseRaw(c.bytes)),c.bytes);
    }else{
      assert.throws(()=>v2.inspect(c.bytes),v2.UnsafeCanonicalInput);
    }
  });
}
for(const [id,domain,ok] of [
  ['DOM-01',DOMAIN,true],
  ['DOM-02','VORNEQ:OFFLINE_ADMIN_STATIC_CANONICAL_V1\0',false],
  ['DOM-03','VORNEQ:OFFLINE_ADMIN_STATIC_CANONICAL_V2',false],
  ['DOM-04','VORNEQ:OFFLINE_ADMIN_STATIC_CANONICAL_V2\0\0',false],
]) {
  test('DOMAIN '+id,()=>{
    const digest=separated(domain,REFERENCE);
    if(ok) assert.equal(digest,BASE_DOMAIN_SHA);
    else assert.notEqual(digest,BASE_DOMAIN_SHA);
  });
}
for(const [id,change,success] of [
  ['POL-01','oldEvidence',false],
  ['POL-02','minimum',false],
  ['POL-03','revoked',false],
  ['POL-04','normal',true],
]) {
  test('POLICY '+id,()=>{
    const e=fixtureEvidence();
    const options={simulatedNow:time};
    if(change==='oldEvidence')
      e.schema='VORNEQ_OFFLINE_ADMIN_CANONICAL_SIMULATION_EVIDENCE_V1';
    if(change==='minimum')options.callerMinimumVersion=2;
    if(change==='revoked')options.callerRevokedVersions=[1];
    if(success){
      const r=v2.assessSimulation(REFERENCE,BASE_DOMAIN_SHA,e,options);
      assert.equal(r.result,v2.NO_AUTHORITY);
      for(const [key,val] of Object.entries(r)) {
        if(key==='authenticated'||key.endsWith('_authenticated')||
           key.endsWith('_verified')||key.endsWith('_authorized'))
          assert.equal(val,false,key);
      }
    } else assert.throws(()=>v2.assessSimulation(
      REFERENCE,BASE_DOMAIN_SHA,e,options),v2.UnsafeCanonicalInput);
  });
}
test('HARD-01 caller cannot inject domain or mutate internal hash domain',()=>{
  assert.equal(Object.hasOwn(v2,'DOMAIN'),false);
  assert.equal(Object.isFrozen(v2),true);
  assert.throws(()=>v2.hashes(REFERENCE,undefined),v2.UnsafeCanonicalInput);
  assert.throws(()=>v2.hashes(REFERENCE,'ANOTHER_DOMAIN'),v2.UnsafeCanonicalInput);
  assert.equal(v2.hashes(REFERENCE).domain,BASE_DOMAIN_SHA);
});
test('HARD-02 prototype injection stays inert, then fails exact schema',()=>{
  const injected=mutate('"digest_algorithm":"SHA-256",',
    '"__proto__":{"polluted":true},"digest_algorithm":"SHA-256",');
  const parsed=v2.parseRaw(injected);
  assert.equal(Object.getPrototypeOf(parsed),null);
  assert.equal(Object.prototype.polluted,undefined);
  assert.throws(()=>v2.inspect(injected),v2.UnsafeCanonicalInput);
  assert.equal(Object.prototype.polluted,undefined);
});
test('HARD-03 invalid and stale simulated times fail',()=>{
  const evidence=fixtureEvidence();
  for(const date of ['2026-10-14T23:59:59Z','2026-10-16T00:00:00Z',
    '2026-02-30T00:00:00Z'])
    assert.throws(()=>v2.assessSimulation(
      REFERENCE,BASE_DOMAIN_SHA,evidence,{simulatedNow:date}),
      v2.UnsafeCanonicalInput);
});
test('HARD-04 frozen inspection report cannot grant authority',()=>{
  const r=v2.inspect(REFERENCE);
  assert.equal(Object.isFrozen(r),true);
  assert.equal(r.authenticated,false);
  assert.equal(r.external_trust_authenticated,false);
  assert.equal(r.package_creation_authorized,false);
  assert.equal(r.runtime_authorized,false);
  assert.equal(Object.values(r).some(Buffer.isBuffer),false);
  assert.throws(()=>{r.runtime_authorized=true},TypeError);
});
test('HARD-05 simulated report remains no-authority even when claims true',()=>{
  const r=v2.assessSimulation(REFERENCE,BASE_DOMAIN_SHA,fixtureEvidence(),
    {simulatedNow:time});
  assert.equal(Object.isFrozen(r),true);
  assert.equal(r.result,'STATIC_SIMULATION_CONTRACT_ONLY');
  assert.equal(r.authenticated,false);
  assert.equal(r.source_provenance_verified,false);
  assert.equal(r.snapshot_verified,false);
  assert.equal(r.network_isolation_verified,false);
  assert.equal(r.transfer_authorized,false);
  assert.equal(r.django_orm_authorized,false);
  assert.equal(r.runtime_authorized,false);
});
test('HARD-06 exact day and year boundaries are calendar-valid',()=>{
  const check=(issued,expires)=>{
    let b=mutate('"issued_at":"2026-10-15T00:00:00Z"',
      '"issued_at":"'+issued+'"');
    return Buffer.from(b.toString('ascii').replace(
      '"expires_at":"2026-10-16T00:00:00Z"',
      '"expires_at":"'+expires+'"'),'ascii');
  };
  for(const [start,end] of [
    ['2024-02-29T00:00:00Z','2024-03-01T00:00:00Z'],
    ['0001-01-01T00:00:00Z','0001-01-02T00:00:00Z'],
    ['9999-12-30T00:00:00Z','9999-12-31T00:00:00Z'],
  ]) assert.doesNotThrow(()=>v2.inspect(check(start,end)));
  for(const [start,end] of [
    ['2025-02-29T00:00:00Z','2025-03-01T00:00:00Z'],
    ['0000-01-01T00:00:00Z','0001-01-02T00:00:00Z'],
    ['2026-10-15T00:00:00Z','2026-10-23T00:00:00Z'],
  ]) assert.throws(()=>v2.inspect(check(start,end)),v2.UnsafeCanonicalInput);
});
test('HARD-07 caller evidence digest is not independent authentication',()=>{
  const copied=Buffer.from(REFERENCE);
  const initial=v2.inspect(REFERENCE);
  copied[0]^=1;
  assert.equal(initial.domain,BASE_DOMAIN_SHA);
  assert.equal(initial.runtime_authorized,false);
  assert.throws(()=>v2.inspect(copied),v2.UnsafeCanonicalInput);
});
