"""Offline VORNEQ V2 Python conformance against independent pinned fixtures.

Run only as: python -B marketplace/test_offline_admin_canonical_v2_golden_vectors.py
Read-only tests: no Django, DB, network, filesystem write or V1 imports.
"""
import datetime
import hashlib
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gold = load_module("vorneq_v2_fixed_golden", "config/offline_admin_canonical_v2_golden_vectors.py")
v2 = load_module("vorneq_v2_contract_under_test", "config/offline_admin_trust_anchor_canonical_contract_v2.py")


class CanonicalV2Python(unittest.TestCase):
    def test_pinned_reference_hashes(self):
        base = gold.REFERENCE_CANONICAL_BYTES
        top = gold.REFERENCE_MAX_VERSION_BYTES
        domain = gold.REFERENCE_DOMAIN
        self.assertEqual(len(base), 2418)
        self.assertEqual(len(top), 2433)
        self.assertEqual(hashlib.sha256(base).hexdigest(),
                         "eec0ab9f4170c680ed0f24602238c2b47d005cc01e3b735ef454832f99a72b2a")
        self.assertEqual(hashlib.sha256(domain + base).hexdigest(),
                         "40c822761ddfda09df74e1aba460e23aea294502e6ce4269207e12d9c007a44f")
        self.assertEqual(hashlib.sha256(top).hexdigest(),
                         "9da5b10eee472c0459304e78c658225bfa180a4c830c150f370a83cdefe5f54c")
        self.assertEqual(hashlib.sha256(domain + top).hexdigest(),
                         "17c8364932d812d338e12081873bebf96e6b5df63f422b56aa57a97e40596650")

    def test_fixture_is_independent_and_fixed(self):
        self.assertEqual(gold.REFERENCE_SCHEMA, "VORNEQ_OFFLINE_ADMIN_CANONICAL_CONTRACT_V2")
        self.assertEqual(gold.REFERENCE_PROFILE, "VORNEQ_JSON_ASCII_SORTED_COMPACT_SAFEINT_V2")
        self.assertEqual(gold.REFERENCE_ANCHOR_SCHEMA, "VORNEQ_OFFLINE_ADMIN_TRUST_ANCHOR_V1")
        self.assertEqual(gold.MAX_VERSION, 9007199254740991)
        self.assertEqual(len(gold.VECTOR_CASES), 30)
        self.assertEqual(len(gold.DOMAIN_CASES), 4)
        self.assertEqual(len(gold.POLICY_CASES), 4)

    def test_canonical_baseline_byte_for_byte(self):
        value = v2.example_static_envelope()
        self.assertTrue(v2.validate_static_envelope(value))
        self.assertEqual(v2.canonical_bytes(value), gold.REFERENCE_CANONICAL_BYTES)
        self.assertEqual(v2.parse_canonical_bytes(gold.REFERENCE_CANONICAL_BYTES), value)
        self.assertEqual(v2.local_simulation_digest(value),
                         gold.REFERENCE_DOMAIN_SHA256)

    def test_max_safe_version_byte_for_byte(self):
        value = v2.example_static_envelope()
        value["monotonic_version"] = 9007199254740991
        self.assertEqual(v2.canonical_bytes(value), gold.REFERENCE_MAX_VERSION_BYTES)
        self.assertEqual(v2.parse_canonical_bytes(gold.REFERENCE_MAX_VERSION_BYTES), value)
        self.assertEqual(v2.local_simulation_digest(value),
                         gold.REFERENCE_MAX_DOMAIN_SHA256)

    def test_all_thirty_canonical_cases(self):
        got_ids = []
        for ident, scope, raw, expected, _reason in gold.VECTOR_CASES:
            with self.subTest(case=ident):
                got_ids.append(ident)
                if expected.startswith(b"ACCEPT"):
                    actual = v2.parse_canonical_bytes(raw)
                    self.assertEqual(v2.canonical_bytes(actual), raw)
                    self.assertIsInstance(actual, dict)
                else:
                    with self.assertRaises(v2.UnsafeCanonicalContract):
                        v2.parse_canonical_bytes(raw)
        self.assertEqual(len(set(got_ids)), 30)

    def test_all_four_domain_cases(self):
        value = v2.example_static_envelope()
        trusted = gold.REFERENCE_DOMAIN
        for ident, raw, supplied_domain, expected in gold.DOMAIN_CASES:
            with self.subTest(case=ident):
                actual = hashlib.sha256(supplied_domain + raw).hexdigest()
                if expected.startswith("MATCH"):
                    self.assertEqual(supplied_domain, trusted)
                    self.assertEqual(actual, v2.local_simulation_digest(value))
                else:
                    self.assertNotEqual(supplied_domain, trusted)
                    self.assertNotEqual(actual, v2.local_simulation_digest(value))
        with self.assertRaises(TypeError):
            v2.local_simulation_digest(value, b"WRONG_DOMAIN")

    def test_all_four_external_policy_cases(self):
        value = v2.example_static_envelope()
        digest = v2.local_simulation_digest(value)
        for ident, _raw, params, expected in gold.POLICY_CASES:
            with self.subTest(case=ident):
                evidence = v2.example_hypothetical_evidence(value)
                options = {
                    "simulated_now": "2026-10-15T12:00:00Z",
                    "caller_minimum_version": 1,
                    "caller_revoked_versions": (),
                }
                if ident == "POL-01":
                    evidence["schema"] = params
                else:
                    options.update(params)
                if expected == "NO_AUTHORITY":
                    decision = v2.assess_static_simulation(value, digest, evidence, **options)
                    self.assertEqual(decision["result"], v2.NO_AUTHORITY)
                    self.assertTrue(all(
                        flag is False for key, flag in decision.items()
                        if key.endswith("_authorized") or key.endswith("_verified") or
                           key.endswith("_authenticated") or key == "authenticated"
                    ))
                else:
                    with self.assertRaises(v2.UnsafeCanonicalContract):
                        v2.assess_static_simulation(value, digest, evidence, **options)

    def test_invalid_caller_digest_and_simulated_time(self):
        value = v2.example_static_envelope()
        evidence = v2.example_hypothetical_evidence(value)
        correct = v2.local_simulation_digest(value)
        for digest, now in (
            ("0" * 64, "2026-10-15T12:00:00Z"),
            (correct, "2026-10-16T00:00:00Z"),
            (correct, "2026-10-14T23:59:59Z"),
            (correct, "2026-02-30T00:00:00Z"),
        ):
            with self.subTest(digest=digest, now=now):
                with self.assertRaises(v2.UnsafeCanonicalContract):
                    v2.assess_static_simulation(value, digest, evidence, simulated_now=now)

    def test_iso_calendar_and_week_limit(self):
        base = gold.REFERENCE_CANONICAL_BYTES
        original_issue = b'"issued_at":"2026-10-15T00:00:00Z"'
        original_expiry = b'"expires_at":"2026-10-16T00:00:00Z"'
        for issue, expiry in (
            (b'"issued_at":"2024-02-29T00:00:00Z"',
             b'"expires_at":"2024-03-01T00:00:00Z"'),
            (b'"issued_at":"0001-01-01T00:00:00Z"',
             b'"expires_at":"0001-01-02T00:00:00Z"'),
            (b'"issued_at":"9999-12-30T00:00:00Z"',
             b'"expires_at":"9999-12-31T00:00:00Z"'),
        ):
            with self.subTest(issue=issue):
                raw = base.replace(original_issue, issue).replace(original_expiry, expiry)
                self.assertEqual(v2.canonical_bytes(v2.parse_canonical_bytes(raw)), raw)
        for issue, expiry in (
            (b'"issued_at":"2025-02-29T00:00:00Z"',
             b'"expires_at":"2025-03-01T00:00:00Z"'),
            (b'"issued_at":"0000-01-01T00:00:00Z"',
             b'"expires_at":"0001-01-02T00:00:00Z"'),
            (b'"issued_at":"2026-10-15T00:00:00Z"',
             b'"expires_at":"2026-10-23T00:00:00Z"'),
        ):
            with self.subTest(issue=issue):
                raw = base.replace(original_issue, issue).replace(original_expiry, expiry)
                with self.assertRaises(v2.UnsafeCanonicalContract):
                    v2.parse_canonical_bytes(raw)

    def test_invalid_bool_instead_of_version(self):
        item = v2.example_static_envelope()
        item["monotonic_version"] = True
        with self.assertRaises(v2.UnsafeCanonicalContract):
            v2.validate_static_envelope(item)

    def test_success_report_is_immutable(self):
        value = v2.example_static_envelope()
        expected_bytes = gold.REFERENCE_CANONICAL_BYTES
        expected_digest = gold.REFERENCE_DOMAIN_SHA256
        report = v2.assess_static_simulation(
            value,
            v2.local_simulation_digest(value),
            v2.example_hypothetical_evidence(value),
            simulated_now="2026-10-15T12:00:00Z",
        )
        original = dict(report)
        self.assertEqual(report["result"], "STATIC_SIMULATION_CONTRACT_ONLY")
        self.assertIs(report["runtime_authorized"], False)
        with self.assertRaises(TypeError):
            report["runtime_authorized"] = True
        with self.assertRaises(TypeError):
            del report["runtime_authorized"]
        with self.assertRaises(TypeError):
            report["new_authority"] = True
        self.assertEqual(dict(report), original)
        for key, flag in report.items():
            if key == "authenticated" or key.endswith(
                ("_authorized", "_verified", "_authenticated")
            ):
                self.assertIs(flag, False, key)
        self.assertEqual(v2.canonical_bytes(value), expected_bytes)
        self.assertEqual(v2.local_simulation_digest(value), expected_digest)

    def test_enforced_no_authority_even_if_all_claims_true(self):
        value = v2.example_static_envelope()
        report = v2.assess_static_simulation(
            value, v2.local_simulation_digest(value),
            v2.example_hypothetical_evidence(value),
            simulated_now="2026-10-15T12:00:00Z"
        )
        self.assertEqual(report["result"], "STATIC_SIMULATION_CONTRACT_ONLY")
        for key in (
            "authenticated", "external_trust_authenticated",
            "source_provenance_verified", "snapshot_verified",
            "network_isolation_verified", "package_creation_authorized",
            "transfer_authorized", "django_orm_authorized", "runtime_authorized",
        ):
            self.assertIs(report[key], False, key)

    def test_digest_global_rebinding_does_not_change_v2_domain(self):
        original_domain = v2.DOMAIN
        original_schema = v2.SCHEMA
        try:
            v2.DOMAIN = b"VORNEQ:MALICIOUS_DOMAIN\x00"
            v2.SCHEMA = "NOT_THE_OWNER_APPROVED_SCHEMA"
            self.assertEqual(
                v2.local_simulation_digest(v2.example_static_envelope()),
                gold.REFERENCE_DOMAIN_SHA256,
            )
        finally:
            v2.DOMAIN = original_domain
            v2.SCHEMA = original_schema

    def test_no_automatic_v1_conversion(self):
        raw = gold.REFERENCE_CANONICAL_BYTES
        altered = raw.replace(
            b'"schema":"VORNEQ_OFFLINE_ADMIN_CANONICAL_CONTRACT_V2"',
            b'"schema":"VORNEQ_OFFLINE_ADMIN_CANONICAL_CONTRACT_V1"',
        )
        with self.assertRaises(v2.UnsafeCanonicalContract):
            v2.parse_canonical_bytes(altered)


if __name__ == "__main__":
    unittest.main(verbosity=2)
