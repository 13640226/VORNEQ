"""VORNEQ Canonical V2: standalone, strict, offline STATIC SIMULATION ONLY.

No real signature, independently authenticated reference, snapshot measurement,
OS guard, network inspection, replay prevention, package/runtime permission.
Do not use this module for an authorization or attestation state transition.
No imports from V1 policy, V2 golden fixtures, Django or filesystem.
"""

import datetime as _datetime
import hashlib as _hashlib
import hmac as _hmac
import re as _re
from types import MappingProxyType as _MappingProxyType

SCHEMA = "VORNEQ_OFFLINE_ADMIN_CANONICAL_CONTRACT_V2"
CANONICALIZATION = "VORNEQ_JSON_ASCII_SORTED_COMPACT_SAFEINT_V2"
EVIDENCE_SCHEMA = "VORNEQ_OFFLINE_ADMIN_CANONICAL_SIMULATION_EVIDENCE_V2"
ALGORITHM = "SHA-256"
DOMAIN = b"VORNEQ:OFFLINE_ADMIN_STATIC_CANONICAL_V2\x00"
NO_AUTHORITY = "STATIC_SIMULATION_CONTRACT_ONLY"
MAX_CANONICAL_BYTES = 32768
MAX_PARSER_DEPTH = 32
MAX_NUMBER_TOKEN = 20
MAX_VERSION = 9007199254740991

class UnsafeCanonicalContract(ValueError):
    """Reject invalid simulated contract input without granting any authority."""


def _make_v2_contract():
    # Capture immutable primitives in closures: rebinding public module globals
    # cannot select another schema, anchor or domain. In-process malicious code
    # execution is explicitly outside this simulation's security guarantees.
    schema = "VORNEQ_OFFLINE_ADMIN_CANONICAL_CONTRACT_V2"
    profile = "VORNEQ_JSON_ASCII_SORTED_COMPACT_SAFEINT_V2"
    evidence_schema = "VORNEQ_OFFLINE_ADMIN_CANONICAL_SIMULATION_EVIDENCE_V2"
    domain = b"VORNEQ:OFFLINE_ADMIN_STATIC_CANONICAL_V2\x00"
    max_version = 9007199254740991
    sha256 = _hashlib.sha256
    freeze_mapping = _MappingProxyType
    compare = _hmac.compare_digest
    fullmatch = _re.fullmatch
    date_type = _datetime.datetime
    timedelta = _datetime.timedelta
    utc = _datetime.timezone.utc
    error_type = UnsafeCanonicalContract
    project = "13640226/VORNEQ"
    purpose = "OFFLINE_ADMIN_STATIC_TESTS_ONLY"
    head = "f64bb717e4dfddcc3832d5f9c7c9f6b998732983"
    validator_path = "config/offline_admin_package_manifest_validator.py"
    validator_sha = "08bc25bb1a417073267ea316ec9e8f7a83591f2679df434051692edad892773d"
    exception_path = "marketplace/admin.py"
    exception_sha = "35b31f0c9a0f4e5830283e3c936df113cde4581ef725ea4c15b8eb48e626cab4"
    anchor_schema = "VORNEQ_OFFLINE_ADMIN_TRUST_ANCHOR_V1"
    files = (
        ("config/__init__.py", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "git-tracked"),
        ("config/isolated_admin_test_guard.py", "e935f1e6bc95ab8225fda8676e1d56fa25acfb555c2fa85c1e850fac9994d21b", "isolated-untracked"),
        ("config/settings_isolated_admin_test.py", "d8b6ed2f5240254e2361cc288b356c1de3afc5117602d6d8863c19dec6ee5e58", "isolated-untracked"),
        ("config/urls_isolated_admin_test.py", "a4629e61a85508b29d0e7e7f493aaf45634717aeceea3c801610d32c0b361251", "isolated-untracked"),
        ("marketplace/__init__.py", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "git-tracked"),
        ("marketplace/admin.py", "35b31f0c9a0f4e5830283e3c936df113cde4581ef725ea4c15b8eb48e626cab4", "git-tracked-modified"),
        ("marketplace/models.py", "d7fb9dd3ce8fa803bf594a3dbac0e94edd26ec0e45fad25a22376b3a6a95f2bb", "git-tracked"),
        ("marketplace/test_admin_moderation_invariants_offline.py", "1ff33927e0c62f3831a2fb92c33cfc8fb70d7521558cb11b7aa0e8c4bd98d476", "isolated-untracked"),
        ("marketplace/test_isolated_admin_settings_static.py", "a92e2ca21b0ac5be6035c8af602288729ce41cba1e715e3f99d350bf2a56fc4c", "isolated-untracked"),
    )
    envelope_keys = (
        "schema", "canonicalization_version", "digest_algorithm",
        "evidence_class", "simulation_only", "project_id", "purpose",
        "source_repository_id", "source_head", "environment_id",
        "snapshot_id", "issued_at", "expires_at", "monotonic_version",
        "nonce", "anchor",
    )
    anchor_keys = (
        "schema", "project", "purpose", "source_head",
        "validator", "worktree_exception", "files",
    )
    evidence_keys = (
        "schema", "evidence_class", "simulation_only", "source",
        "requested_stage", "contract_sha256", "hypothetical_checks",
        "external_trust_authenticated", "signature_verified",
        "os_measurements_verified", "snapshot_verified",
        "runtime_authorized",
    )
    check_keys = (
        "independent_reference_available",
        "signature_or_owner_reference_reviewed",
        "source_git_provenance_checked",
        "snapshot_membership_checked",
        "snapshot_bytes_checked",
        "snapshot_write_protection_checked",
        "network_isolation_checked",
        "secrets_isolation_checked",
    )

    def deny(reason):
        raise error_type(reason)

    def exact_keys(data, expected, label):
        if type(data) is not dict or len(data) != len(expected) or set(data) != set(expected):
            deny("Invalid exact keys/type: " + label)

    def exact(value, expected, label):
        if type(value) is not type(expected) or value != expected:
            deny("Invalid value: " + label)

    def hex_digest(value, length, label):
        if type(value) is not str or fullmatch("[0-9a-f]{%d}" % length, value) is None:
            deny("Invalid hexadecimal " + label)

    def timestamp(value):
        if type(value) is not str or fullmatch(
            "[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
            value,
        ) is None:
            deny("Invalid UTC format")
        try:
            year = int(value[:4])
            if not 1 <= year <= 9999:
                deny("UTC year must be 0001..9999")
            return date_type(
                year, int(value[5:7]), int(value[8:10]),
                int(value[11:13]), int(value[14:16]), int(value[17:19]),
                tzinfo=utc,
            )
        except (ValueError, OverflowError) as exc:
            raise error_type("Invalid Gregorian UTC timestamp") from exc

    def validate_anchor(anchor):
        exact_keys(anchor, anchor_keys, "pinned anchor")
        for key, expect in (
            ("schema", anchor_schema), ("project", project),
            ("purpose", purpose), ("source_head", head),
        ):
            exact(anchor[key], expect, "anchor." + key)
        for key, path, digest in (
            ("validator", validator_path, validator_sha),
            ("worktree_exception", exception_path, exception_sha),
        ):
            item = anchor[key]
            exact_keys(item, ("path", "sha256"), "anchor." + key)
            exact(item["path"], path, key + ".path")
            hex_digest(item["sha256"], 64, key + ".sha256")
            exact(item["sha256"], digest, key + ".sha256")
        rows = anchor["files"]
        if type(rows) is not list or len(rows) != 9:
            deny("Expected nine pinned ordered file entries")
        for n, (entry, pinned) in enumerate(zip(rows, files)):
            exact_keys(entry, ("path", "sha256", "origin"), "file entry")
            for key, expected in zip(("path", "sha256", "origin"), pinned):
                exact(entry[key], expected, "files[%d].%s" % (n, key))
            hex_digest(entry["sha256"], 64, "file digest")

    def validate_static_envelope(value):
        """Validate V2 schema and OPTION_A anchor; no authenticity is implied."""
        exact_keys(value, envelope_keys, "V2 envelope")
        for key, expected in (
            ("schema", schema), ("canonicalization_version", profile),
            ("digest_algorithm", "SHA-256"), ("evidence_class", "SIMULATED"),
            ("simulation_only", True), ("project_id", project),
            ("purpose", purpose), ("source_repository_id", project),
            ("source_head", head), ("environment_id", "SIMULATED_ENVIRONMENT_ONLY"),
            ("snapshot_id", "SIMULATED_SNAPSHOT_ONLY"),
        ):
            exact(value[key], expected, "envelope." + key)
        hex_digest(value["nonce"], 32, "nonce")
        version = value["monotonic_version"]
        if type(version) is not int or not 1 <= version <= max_version:
            deny("Version outside exact cross-language safe range")
        start = timestamp(value["issued_at"])
        end = timestamp(value["expires_at"])
        if not start < end or end - start > timedelta(days=7):
            deny("Invalid simulation issuance interval")
        validate_anchor(value["anchor"])
        exact(value["anchor"]["project"], value["project_id"], "project binding")
        exact(value["anchor"]["source_head"], value["source_head"], "HEAD binding")
        return True

    def encode(value, depth=0):
        if depth > 32:
            deny("Maximum canonical nesting depth exceeded")
        if type(value) is str:
            if any(ord(c) < 32 or ord(c) > 126 or c in ('"', '\\') for c in value):
                deny("Noncanonical ASCII string")
            return b'"' + value.encode("ascii") + b'"'
        if type(value) is bool:
            return b"true" if value else b"false"
        if type(value) is int:
            if not 1 <= value <= max_version:
                deny("Unsafe canonical integer")
            return str(value).encode("ascii")
        if type(value) is list:
            return b"[" + b",".join(encode(x, depth + 1) for x in value) + b"]"
        if type(value) is dict:
            result = []
            for key in sorted(value):
                if type(key) is not str:
                    deny("Nonstring key")
                if any(ord(c) < 32 or ord(c) > 126 or c in ('"', '\\') for c in key):
                    deny("Noncanonical object key")
                result.append(b'"' + key.encode("ascii") + b'":' +
                              encode(value[key], depth + 1))
            return b"{" + b",".join(result) + b"}"
        deny("Invalid canonical data type")

    def canonical_bytes(value):
        """V2's exact ASCII sorted compact encoding (no V1 encoder import)."""
        validate_static_envelope(value)
        encoded = encode(value, 0)
        if not 1 <= len(encoded) <= 32768:
            deny("Canonical bytes outside permitted size")
        return encoded

    def parse_canonical_bytes(raw):
        """Bounded strict raw byte parser: no json.loads or lossy Number coercion."""
        if type(raw) is not bytes or not 1 <= len(raw) <= 32768:
            deny("Invalid raw byte type or size")
        if any(ch < 32 or ch > 126 for ch in raw):
            deny("Nonprinting ASCII, Unicode bytes or BOM")
        cursor = 0
        size = len(raw)

        def parse_string():
            nonlocal cursor
            if cursor >= size or raw[cursor] != 34:
                deny("Expected JSON string")
            cursor += 1
            start = cursor
            while cursor < size:
                ch = raw[cursor]
                if ch == 34:
                    result = raw[start:cursor].decode("ascii")
                    cursor += 1
                    return result
                if ch == 92:
                    deny("String escapes prohibited in canonical profile")
                cursor += 1
            deny("Unterminated string")

        def parse_value(depth):
            nonlocal cursor
            if depth > 32:
                deny("JSON depth exceeds 32")
            if cursor >= size:
                deny("Unexpected end of JSON")
            token = raw[cursor]
            if token == 34:
                return parse_string()
            if token == 123:
                cursor += 1
                result = {}
                if cursor < size and raw[cursor] == 125:
                    cursor += 1
                    return result
                while True:
                    key = parse_string()
                    if key in result:
                        deny("Duplicate object member")
                    if cursor >= size or raw[cursor] != 58:
                        deny("Missing colon")
                    cursor += 1
                    result[key] = parse_value(depth + 1)
                    if cursor >= size:
                        deny("Unterminated JSON object")
                    sep = raw[cursor]
                    cursor += 1
                    if sep == 125:
                        return result
                    if sep != 44:
                        deny("Invalid object separator")
            if token == 91:
                cursor += 1
                result = []
                if cursor < size and raw[cursor] == 93:
                    cursor += 1
                    return result
                while True:
                    result.append(parse_value(depth + 1))
                    if cursor >= size:
                        deny("Unterminated JSON array")
                    sep = raw[cursor]
                    cursor += 1
                    if sep == 93:
                        return result
                    if sep != 44:
                        deny("Invalid array separator")
            for literal, val in ((b"true", True), (b"false", False)):
                if raw.startswith(literal, cursor):
                    cursor += len(literal)
                    return val
            if token == 45 or 48 <= token <= 57:
                start = cursor
                if token == 45:
                    cursor += 1
                    if cursor >= size:
                        deny("Truncated negative integer")
                if raw[cursor] == 48:
                    cursor += 1
                    if cursor < size and 48 <= raw[cursor] <= 57:
                        deny("Leading zero")
                elif 49 <= raw[cursor] <= 57:
                    while cursor < size and 48 <= raw[cursor] <= 57:
                        cursor += 1
                else:
                    deny("Malformed integer lexeme")
                if cursor < size and raw[cursor] in (46, 69, 101):
                    deny("Float/exponent prohibited")
                digits = raw[start:cursor]
                if len(digits) > 20:
                    deny("Numeric token length exceeds 20")
                number = int(digits)
                if not 1 <= number <= max_version:
                    deny("Invalid or unsafe integer")
                return number
            deny("Unexpected JSON token")

        parsed = parse_value(0)
        if cursor != size:
            deny("Trailing or noncanonical JSON bytes")
        if canonical_bytes(parsed) != raw:
            deny("Noncanonical JSON byte representation")
        return parsed

    def local_simulation_digest(value):
        """SHA256(V2 domain || V2 bytes), never a trusted signature."""
        return sha256(domain + canonical_bytes(value)).hexdigest()

    def example_static_envelope():
        """Explicit synthetic in-memory fixture, not an authenticated anchor."""
        return {
            "schema": schema, "canonicalization_version": profile,
            "digest_algorithm": "SHA-256", "evidence_class": "SIMULATED",
            "simulation_only": True, "project_id": project, "purpose": purpose,
            "source_repository_id": project, "source_head": head,
            "environment_id": "SIMULATED_ENVIRONMENT_ONLY",
            "snapshot_id": "SIMULATED_SNAPSHOT_ONLY",
            "issued_at": "2026-10-15T00:00:00Z",
            "expires_at": "2026-10-16T00:00:00Z",
            "monotonic_version": 1,
            "nonce": "0123456789abcdef0123456789abcdef",
            "anchor": {
                "schema": anchor_schema, "project": project, "purpose": purpose,
                "source_head": head,
                "validator": {"path": validator_path, "sha256": validator_sha},
                "worktree_exception": {"path": exception_path, "sha256": exception_sha},
                "files": [
                    {"path": path, "sha256": digest, "origin": origin}
                    for path, digest, origin in files
                ],
            },
        }

    def example_hypothetical_evidence(value):
        """Caller-owned CLAIMS, not independently measured facts."""
        return {
            "schema": evidence_schema, "evidence_class": "SIMULATED",
            "simulation_only": True, "source": "IN_MEMORY_FIXTURE",
            "requested_stage": "STATIC_CONTRACT_CHECK_ONLY",
            "contract_sha256": local_simulation_digest(value),
            "hypothetical_checks": {key: True for key in check_keys},
            "external_trust_authenticated": False,
            "signature_verified": False, "os_measurements_verified": False,
            "snapshot_verified": False, "runtime_authorized": False,
        }

    def assess_static_simulation(
        value, caller_reference_digest, evidence, *,
        simulated_now, caller_minimum_version=1, caller_revoked_versions=(),
    ):
        """Only simulate; caller digest/time/revocations never confer authority."""
        validate_static_envelope(value)
        hex_digest(caller_reference_digest, 64, "caller reference digest")
        actual = local_simulation_digest(value)
        if not compare(caller_reference_digest, actual):
            deny("Caller-supplied digest mismatch")
        now = timestamp(simulated_now)
        if not timestamp(value["issued_at"]) <= now < timestamp(value["expires_at"]):
            deny("Outside caller-supplied simulated time")
        if type(caller_minimum_version) is not int or not 1 <= caller_minimum_version <= max_version:
            deny("Invalid caller-supplied version floor")
        if type(caller_revoked_versions) not in (list, tuple):
            deny("Invalid caller-supplied revocation collection")
        revoked = set()
        for n in caller_revoked_versions:
            if type(n) is not int or not 1 <= n <= max_version or n in revoked:
                deny("Invalid or duplicate caller revocation")
            revoked.add(n)
        if value["monotonic_version"] < caller_minimum_version or value["monotonic_version"] in revoked:
            deny("Stale or caller-revoked version in simulation")
        exact_keys(evidence, evidence_keys, "simulation evidence")
        for key, expected in (
            ("schema", evidence_schema), ("evidence_class", "SIMULATED"),
            ("simulation_only", True), ("source", "IN_MEMORY_FIXTURE"),
            ("requested_stage", "STATIC_CONTRACT_CHECK_ONLY"),
            ("contract_sha256", actual),
            ("external_trust_authenticated", False), ("signature_verified", False),
            ("os_measurements_verified", False), ("snapshot_verified", False),
            ("runtime_authorized", False),
        ):
            exact(evidence[key], expected, "evidence." + key)
        checks = evidence["hypothetical_checks"]
        exact_keys(checks, check_keys, "hypothetical claims")
        if any(type(checks[k]) is not bool or checks[k] is not True for k in check_keys):
            deny("Invalid or missing hypothetical claim")
        return freeze_mapping({
            "result": "STATIC_SIMULATION_CONTRACT_ONLY",
            "evidence_class": "SIMULATED", "authenticated": False,
            "external_trust_authenticated": False, "source_provenance_verified": False,
            "snapshot_verified": False, "network_isolation_verified": False,
            "package_creation_authorized": False, "transfer_authorized": False,
            "django_orm_authorized": False, "runtime_authorized": False,
        })

    return (
        validate_static_envelope, canonical_bytes, parse_canonical_bytes,
        local_simulation_digest, assess_static_simulation,
        example_static_envelope, example_hypothetical_evidence,
    )


(
    validate_static_envelope, canonical_bytes, parse_canonical_bytes,
    local_simulation_digest, assess_static_simulation,
    example_static_envelope, example_hypothetical_evidence,
) = _make_v2_contract()
del _make_v2_contract
