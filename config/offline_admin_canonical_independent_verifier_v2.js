'use strict';
// Standalone VORNEQ V2 offline canonical contract, STATIC SIMULATION ONLY.
// NO signature, external trust, real snapshot/OS proof, real replay protection,
// network use, filesystem use, Django, package/transfer/runtime authority.
// Does not import V1, Python V2, golden vectors, external packages or test code.
const { createHash, timingSafeEqual } = require('node:crypto');

const SCHEMA = 'VORNEQ_OFFLINE_ADMIN_CANONICAL_CONTRACT_V2';
const PROFILE = 'VORNEQ_JSON_ASCII_SORTED_COMPACT_SAFEINT_V2';
const EVIDENCE_SCHEMA = 'VORNEQ_OFFLINE_ADMIN_CANONICAL_SIMULATION_EVIDENCE_V2';
const NO_AUTHORITY = 'STATIC_SIMULATION_CONTRACT_ONLY';
const SCHEMA_VALID_RESULT = 'STATIC_CANONICAL_SCHEMA_VALID';
const DOMAIN_PREFIX_ASCII = 'VORNEQ:OFFLINE_ADMIN_STATIC_CANONICAL_V2\0';
const PROJECT = '13640226/VORNEQ';
const PURPOSE = 'OFFLINE_ADMIN_STATIC_TESTS_ONLY';
const SOURCE_HEAD = 'f64bb717e4dfddcc3832d5f9c7c9f6b998732983';
const MAX_BYTES = 32768;
const MAX_DEPTH = 32;
const MAX_NUMBER_TOKEN = 20;
const MAX_VERSION = Number.MAX_SAFE_INTEGER;
const ALGORITHM = 'SHA-256';
const MS_PER_DAY = 24 * 60 * 60 * 1000;

const FIXED_FILES = Object.freeze([
  Object.freeze(["config/__init__.py", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "git-tracked"]),
  Object.freeze(["config/isolated_admin_test_guard.py", "e935f1e6bc95ab8225fda8676e1d56fa25acfb555c2fa85c1e850fac9994d21b", "isolated-untracked"]),
  Object.freeze(["config/settings_isolated_admin_test.py", "d8b6ed2f5240254e2361cc288b356c1de3afc5117602d6d8863c19dec6ee5e58", "isolated-untracked"]),
  Object.freeze(["config/urls_isolated_admin_test.py", "a4629e61a85508b29d0e7e7f493aaf45634717aeceea3c801610d32c0b361251", "isolated-untracked"]),
  Object.freeze(["marketplace/__init__.py", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "git-tracked"]),
  Object.freeze(["marketplace/admin.py", "35b31f0c9a0f4e5830283e3c936df113cde4581ef725ea4c15b8eb48e626cab4", "git-tracked-modified"]),
  Object.freeze(["marketplace/models.py", "d7fb9dd3ce8fa803bf594a3dbac0e94edd26ec0e45fad25a22376b3a6a95f2bb", "git-tracked"]),
  Object.freeze(["marketplace/test_admin_moderation_invariants_offline.py", "1ff33927e0c62f3831a2fb92c33cfc8fb70d7521558cb11b7aa0e8c4bd98d476", "isolated-untracked"]),
  Object.freeze(["marketplace/test_isolated_admin_settings_static.py", "a92e2ca21b0ac5be6035c8af602288729ce41cba1e715e3f99d350bf2a56fc4c", "isolated-untracked"]),
]);
const ENVELOPE_KEYS = Object.freeze([
  'schema', 'canonicalization_version', 'digest_algorithm',
  'evidence_class', 'simulation_only', 'project_id', 'purpose',
  'source_repository_id', 'source_head', 'environment_id', 'snapshot_id',
  'issued_at', 'expires_at', 'monotonic_version', 'nonce', 'anchor'
]);
const ANCHOR_KEYS = Object.freeze([
  'schema', 'project', 'purpose', 'source_head',
  'validator', 'worktree_exception', 'files'
]);
const EVIDENCE_KEYS = Object.freeze([
  'schema', 'evidence_class', 'simulation_only', 'source',
  'requested_stage', 'contract_sha256', 'hypothetical_checks',
  'external_trust_authenticated', 'signature_verified',
  'os_measurements_verified', 'snapshot_verified', 'runtime_authorized'
]);
const HYPOTHETICAL_CHECKS = Object.freeze([
  'independent_reference_available',
  'signature_or_owner_reference_reviewed',
  'source_git_provenance_checked',
  'snapshot_membership_checked',
  'snapshot_bytes_checked',
  'snapshot_write_protection_checked',
  'network_isolation_checked',
  'secrets_isolation_checked'
]);

class UnsafeCanonicalInput extends Error {
  constructor(message) {
    super(message);
    this.name = 'UnsafeCanonicalInput';
  }
}
function reject(message) { throw new UnsafeCanonicalInput(message); }
function isPlainObject(x) {
  return x !== null && typeof x === 'object' && !Array.isArray(x) &&
    (Object.getPrototypeOf(x) === null ||
     Object.getPrototypeOf(x) === Object.prototype);
}
function exactKeys(obj, expected, label) {
  if (!isPlainObject(obj)) reject('Object required: ' + label);
  const keys = Object.keys(obj);
  if (keys.length !== expected.length ||
      keys.some(key => !expected.includes(key))) reject('Invalid exact keys: ' + label);
}
function exact(value, required, label) {
  if (value !== required || typeof value !== typeof required)
    reject('Invalid pinned value: ' + label);
}
function digest64(s, label) {
  if (typeof s !== 'string' || !/^[0-9a-f]{64}$/.test(s))
    reject('Invalid sha256: ' + label);
}
function asciiString(s) {
  if (typeof s !== 'string') reject('String required');
  for (let j = 0; j < s.length; j++) {
    const n = s.charCodeAt(j);
    if (n < 0x20 || n > 0x7e || n === 0x22 || n === 0x5c)
      reject('Invalid canonical ASCII string');
  }
}
function timestamp(s) {
  if (typeof s !== 'string' ||
      !/^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$/.test(s))
    reject('Invalid UTC timestamp grammar');
  const year = Number(s.slice(0, 4));
  if (year < 1 || year > 9999) reject('Invalid common calendar year');
  const value = Date.parse(s);
  if (!Number.isFinite(value) ||
      new Date(value).toISOString() !== s.slice(0, 19) + '.000Z')
    reject('Invalid Gregorian UTC timestamp');
  return value;
}

function validateAnchor(anchor) {
  exactKeys(anchor, ANCHOR_KEYS, 'fixed OPTION_A anchor');
  for (const [field, value] of [
    ['schema', 'VORNEQ_OFFLINE_ADMIN_TRUST_ANCHOR_V1'],
    ['project', PROJECT], ['purpose', PURPOSE], ['source_head', SOURCE_HEAD]
  ]) exact(anchor[field], value, 'anchor.' + field);
  for (const [name, path, digest] of [
    ['validator', 'config/offline_admin_package_manifest_validator.py',
     '08bc25bb1a417073267ea316ec9e8f7a83591f2679df434051692edad892773d'],
    ['worktree_exception', 'marketplace/admin.py',
     '35b31f0c9a0f4e5830283e3c936df113cde4581ef725ea4c15b8eb48e626cab4']
  ]) {
    const entry = anchor[name];
    exactKeys(entry, ['path', 'sha256'], name);
    exact(entry.path, path, name + '.path');
    digest64(entry.sha256, name);
    exact(entry.sha256, digest, name + '.sha256');
  }
  if (!Array.isArray(anchor.files) || anchor.files.length !== FIXED_FILES.length)
    reject('Exactly nine pinned ordered manifest rows required');
  for (let i = 0; i < FIXED_FILES.length; i++) {
    const row = anchor.files[i];
    const fixed = FIXED_FILES[i];
    exactKeys(row, ['path', 'sha256', 'origin'], 'file row');
    exact(row.path, fixed[0], 'row path');
    digest64(row.sha256, 'row digest');
    exact(row.sha256, fixed[1], 'row digest');
    exact(row.origin, fixed[2], 'row provenance declaration');
  }
}
function validateStaticEnvelope(value) {
  exactKeys(value, ENVELOPE_KEYS, 'V2 envelope');
  for (const [key, expected] of [
    ['schema', SCHEMA], ['canonicalization_version', PROFILE],
    ['digest_algorithm', ALGORITHM], ['evidence_class', 'SIMULATED'],
    ['simulation_only', true], ['project_id', PROJECT], ['purpose', PURPOSE],
    ['source_repository_id', PROJECT], ['source_head', SOURCE_HEAD],
    ['environment_id', 'SIMULATED_ENVIRONMENT_ONLY'],
    ['snapshot_id', 'SIMULATED_SNAPSHOT_ONLY']
  ]) exact(value[key], expected, key);
  if (typeof value.nonce !== 'string' ||
      !/^[0-9a-f]{32}$/.test(value.nonce)) reject('Invalid nonce');
  if (!Number.isSafeInteger(value.monotonic_version) ||
      value.monotonic_version < 1 || value.monotonic_version > MAX_VERSION)
    reject('Integer outside common positive safe range');
  const begin = timestamp(value.issued_at);
  const end = timestamp(value.expires_at);
  if (!(begin < end) || end - begin > 7 * MS_PER_DAY)
    reject('Invalid simulated issuance window');
  validateAnchor(value.anchor);
  exact(value.anchor.project, value.project_id, 'project binding');
  exact(value.anchor.source_head, value.source_head, 'source binding');
  return true;
}

// Restricted ASCII JSON parser. No JSON.parse, no Unicode escapes, no Number
// coercion before the raw integer's exact BigInt boundary checks.
function parseRaw(raw) {
  if (arguments.length !== 1 || !Buffer.isBuffer(raw) ||
      raw.length < 1 || raw.length > MAX_BYTES) reject('Invalid input bytes');
  for (const b of raw) if (b < 0x20 || b > 0x7e)
    reject('Nonprinting or non-ASCII bytes/BOM');
  const s = raw.toString('ascii');
  let i = 0;
  function parseString() {
    if (i >= s.length || s[i] !== '"') reject('Expected JSON string');
    i++;
    const start = i;
    while (i < s.length) {
      const c = s[i++];
      if (c === '"') return s.slice(start, i - 1);
      if (c === '\\') reject('Canonical escapes forbidden');
    }
    reject('Unterminated JSON string');
  }
  function value(depth) {
    if (depth > MAX_DEPTH) reject('Parser depth exceeds 32');
    if (i >= s.length) reject('Unexpected end of raw JSON');
    const token = s[i];
    if (token === '"') return parseString();
    if (token === '{') {
      i++;
      const output = Object.create(null);
      if (s[i] === '}') { i++; return output; }
      while (true) {
        const key = parseString();
        if (Object.hasOwn(output, key)) reject('Duplicate object member');
        if (s[i++] !== ':') reject('Missing JSON colon');
        Object.defineProperty(output, key, {
          value: value(depth + 1), enumerable: true,
          writable: true, configurable: true
        });
        if (i >= s.length) reject('Unterminated object');
        const sep = s[i++];
        if (sep === '}') return output;
        if (sep !== ',') reject('Invalid object delimiter');
      }
    }
    if (token === '[') {
      i++;
      const output = [];
      if (s[i] === ']') { i++; return output; }
      while (true) {
        output.push(value(depth + 1));
        if (i >= s.length) reject('Unterminated array');
        const sep = s[i++];
        if (sep === ']') return output;
        if (sep !== ',') reject('Invalid array delimiter');
      }
    }
    for (const [rawToken, jsValue] of [['true', true], ['false', false]]) {
      if (s.startsWith(rawToken, i)) {
        i += rawToken.length;
        return jsValue;
      }
    }
    if (token === '-' || (token >= '0' && token <= '9')) {
      const start = i;
      if (s[i] === '-') { i++; if (i >= s.length) reject('Truncated integer'); }
      if (s[i] === '0') {
        i++;
        if (s[i] >= '0' && s[i] <= '9') reject('Leading zero');
      } else if (s[i] >= '1' && s[i] <= '9') {
        while (i < s.length && s[i] >= '0' && s[i] <= '9') i++;
      } else reject('Invalid integer token');
      if (s[i] === '.' || s[i] === 'e' || s[i] === 'E')
        reject('Float/exponent prohibited');
      const lexeme = s.slice(start, i);
      if (lexeme.length > MAX_NUMBER_TOKEN) reject('Oversized numeric token');
      const n = BigInt(lexeme);
      if (n < 1n || n > BigInt(MAX_VERSION)) reject('Out-of-range integer');
      return Number(n);
    }
    reject('Invalid canonical JSON token');
  }
  const parsed = value(0);
  if (i !== s.length) reject('Trailing/noncanonical input bytes');
  return parsed;
}
function encodeValue(value, depth = 0) {
  if (depth > MAX_DEPTH) reject('Encoder depth exceeds 32');
  if (typeof value === 'string') {
    asciiString(value);
    return '"' + value + '"';
  }
  if (value === true) return 'true';
  if (value === false) return 'false';
  if (typeof value === 'number') {
    if (!Number.isSafeInteger(value) || value < 1 || value > MAX_VERSION)
      reject('Invalid positive safe integer');
    return String(value);
  }
  if (Array.isArray(value)) {
    return '[' + value.map(v => encodeValue(v, depth + 1)).join(',') + ']';
  }
  if (isPlainObject(value)) {
    const parts = [];
    for (const key of Object.keys(value).sort()) {
      asciiString(key);
      parts.push('"' + key + '":' + encodeValue(value[key], depth + 1));
    }
    return '{' + parts.join(',') + '}';
  }
  reject('Invalid value in canonical encoder');
}
function canonicalizeObject(value) {
  validateStaticEnvelope(value);
  const text = encodeValue(value, 0);
  const result = Buffer.from(text, 'ascii');
  if (result.length < 1 || result.length > MAX_BYTES)
    reject('Canonical size outside permitted range');
  return result;
}
function hashes(bytes) {
  // Exactly one Buffer. A second argument, even undefined, is a hard failure.
  // Domain remains private primitive string; never export a mutable Buffer.
  if (arguments.length !== 1 || !Buffer.isBuffer(bytes) ||
      bytes.length < 1 || bytes.length > MAX_BYTES) reject('Invalid hash API arguments');
  return Object.freeze({
    raw: createHash('sha256').update(bytes).digest('hex'),
    domain: createHash('sha256')
      .update(DOMAIN_PREFIX_ASCII, 'ascii')
      .update(bytes).digest('hex')
  });
}
function inspect(raw) {
  if (arguments.length !== 1) reject('Invalid inspect arguments');
  const object = parseRaw(raw);
  const canonical = canonicalizeObject(object);
  if (!raw.equals(canonical)) reject('Noncanonical input bytes');
  const digests = hashes(canonical);
  // Do not expose a mutable Buffer or the untrusted parsed object in report.
  return Object.freeze({
    result: SCHEMA_VALID_RESULT,
    evidence_class: 'SIMULATED',
    raw: digests.raw, domain: digests.domain,
    authenticated: false,
    external_trust_authenticated: false,
    source_provenance_verified: false,
    snapshot_verified: false,
    network_isolation_verified: false,
    package_creation_authorized: false,
    transfer_authorized: false,
    django_orm_authorized: false,
    runtime_authorized: false
  });
}
function matchDigest(a, b) {
  if (arguments.length !== 2) reject('Invalid digest comparison arguments');
  digest64(a, 'left');
  digest64(b, 'right');
  return timingSafeEqual(Buffer.from(a, 'hex'), Buffer.from(b, 'hex'));
}
function assessSimulation(
  raw, callerDigest, evidence,
  { simulatedNow, callerMinimumVersion = 1, callerRevokedVersions = [] } = {}
) {
  if (arguments.length > 4) reject('Unexpected simulation arguments');
  const report = inspect(raw);
  if (!matchDigest(callerDigest, report.domain))
    reject('Caller-provided digest mismatch');
  const object = parseRaw(raw);
  const now = timestamp(simulatedNow);
  const begin = timestamp(object.issued_at);
  const end = timestamp(object.expires_at);
  if (now < begin || now >= end) reject('Outside simulated time');
  if (!Number.isSafeInteger(callerMinimumVersion) ||
      callerMinimumVersion < 1 || callerMinimumVersion > MAX_VERSION)
    reject('Invalid caller version floor');
  if (!Array.isArray(callerRevokedVersions) ||
      new Set(callerRevokedVersions).size !== callerRevokedVersions.length ||
      callerRevokedVersions.some(n => !Number.isSafeInteger(n) ||
         n < 1 || n > MAX_VERSION))
    reject('Invalid caller revocation list');
  if (object.monotonic_version < callerMinimumVersion ||
      callerRevokedVersions.includes(object.monotonic_version))
    reject('Simulated stale or caller-revoked version');
  exactKeys(evidence, EVIDENCE_KEYS, 'hypothetical evidence');
  for (const [key, expected] of [
    ['schema', EVIDENCE_SCHEMA], ['evidence_class', 'SIMULATED'],
    ['simulation_only', true], ['source', 'IN_MEMORY_FIXTURE'],
    ['requested_stage', 'STATIC_CONTRACT_CHECK_ONLY'],
    ['contract_sha256', report.domain],
    ['external_trust_authenticated', false], ['signature_verified', false],
    ['os_measurements_verified', false], ['snapshot_verified', false],
    ['runtime_authorized', false]
  ]) exact(evidence[key], expected, key);
  exactKeys(evidence.hypothetical_checks, HYPOTHETICAL_CHECKS, 'claimed checks');
  for (const key of HYPOTHETICAL_CHECKS)
    exact(evidence.hypothetical_checks[key], true, key);
  return Object.freeze({
    result: NO_AUTHORITY, evidence_class: 'SIMULATED', authenticated: false,
    external_trust_authenticated: false,
    source_provenance_verified: false, snapshot_verified: false,
    network_isolation_verified: false, package_creation_authorized: false,
    transfer_authorized: false, django_orm_authorized: false,
    runtime_authorized: false
  });
}
// Freeze public exports, including data, and do not expose DOMAIN or mutable
// fixed manifest data. No public function accepts an alternative hash domain.
module.exports = Object.freeze({
  SCHEMA, PROFILE, EVIDENCE_SCHEMA, MAX_BYTES, MAX_DEPTH, MAX_NUMBER_TOKEN,
  NO_AUTHORITY, SCHEMA_VALID_RESULT, UnsafeCanonicalInput, parseRaw,
  validateStaticEnvelope, canonicalizeObject, hashes, inspect, matchDigest,
  assessSimulation
});
