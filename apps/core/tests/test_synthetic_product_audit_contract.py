"""Offline contract tests for the C02 synthetic-product read-only audit SQL.

No database connections are created by these tests.
"""
import os
import re
import unittest
from pathlib import Path

NAME = "P0_SYNTHETIC_PRODUCTS_READONLY_AUDIT_V1_2.sql"
DEFAULT_PATH = Path(__file__).resolve().parents[3] / "docs" / "audits" / NAME
SQL_PATH = Path(os.environ.get("VORNEQ_AUDIT_SQL_TEST_PATH", str(DEFAULT_PATH)))


class SyntheticProductAuditSQLContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SQL_PATH.read_text(encoding="utf-8")
        cls.sql = re.sub(r"(?m)^\s*--[^\n]*(?:\n|$)", "", cls.source)
        cls.statements = [
            part.strip()
            for part in cls.sql.split(";")
            if part.strip()
        ]

    def test_expected_statement_sequence(self):
        self.assertEqual(len(self.statements), 11)
        self.assertEqual(self.statements[0], "BEGIN TRANSACTION READ ONLY")
        self.assertRegex(self.statements[1], r"^SET LOCAL statement_timeout\s*=\s*'15s'$")
        self.assertRegex(self.statements[2], r"^SET LOCAL lock_timeout\s*=\s*'3s'$")
        self.assertEqual(self.statements[-1], "ROLLBACK")
        for statement in self.statements[3:-1]:
            self.assertRegex(statement, r"(?is)^(SELECT|WITH)\b")

    def test_read_only_with_no_dml_ddl(self):
        forbidden = r"(?i)\b(?:INSERT|UPDATE|DELETE|TRUNCATE|ALTER|CREATE|DROP|GRANT|REVOKE|COPY|VACUUM|DO|CALL|EXECUTE)\b"
        self.assertIsNone(re.search(forbidden, self.sql))
        self.assertIn("current_setting('transaction_read_only')", self.sql)

    def test_fail_closed_identity_guard_precedes_fixture_queries(self):
        self.assertIn("runtime_identity_guard", self.statements[4])
        self.assertIn("current_database() = 'vorneq_production_db'", self.statements[4])
        self.assertIn("current_user = 'vorneq_production_db_user'", self.statements[4])
        self.assertIn("current_setting('transaction_read_only') = 'on'", self.statements[4])
        self.assertLess(self.sql.index("runtime_identity_guard"), self.sql.index("FROM marketplace_product"))

    def test_all_query_sections_present(self):
        for query in range(6):
            with self.subTest(query=query):
                self.assertRegex(self.source, rf"(?m)^-- Q{query}:")
        self.assertIn("-- Q0G:", self.source)

    def test_synthetic_markers_and_provenance_limit(self):
        for marker in ("vorneq-benchmark-%", "inspect-staging-smoke%", "vorneq-benchmark-seed", "vorneq-inspect-smoke"):
            self.assertIn(marker, self.source)
        self.assertIn("not immutable provenance", self.source)

    def test_dependency_expiry_and_utc(self):
        self.assertIn("e.expires_at IS NULL OR e.expires_at > now()", self.source)
        self.assertIn("AT TIME ZONE 'UTC'", self.source)
        for relation in ("core_entitlement", "marketplace_productreview", "core_artifactbinding"):
            self.assertIn(relation, self.sql)

    def test_authorization_and_no_secret_export(self):
        self.assertIn("SEPARATE OWNER C02 EXECUTION DECISION", self.source)
        self.assertIn("ON_ERROR_STOP on", self.source)
        self.assertNotRegex(self.sql, r"(?i)\b(?:SELECT\s+password|pg_read_file|pg_ls_dir|dblink|http_post)\b")


if __name__ == "__main__":
    unittest.main()
