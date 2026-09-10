from types import SimpleNamespace

from django.db import IntegrityError
from django.test import SimpleTestCase

from apps.core.constants.handles import RESERVED_HANDLES
from apps.core.services.handles import (
    _extract_violated_constraint,
    _is_handle_uniqueness_conflict,
    _is_one_handle_per_identity_conflict,
    _truncate_for_suffix,
    normalize_handle,
)


class NormalizeHandleTests(SimpleTestCase):
    def test_lowercases(self):
        self.assertEqual(normalize_handle("Alice"), "alice")

    def test_whitespace_becomes_dash(self):
        self.assertEqual(normalize_handle("alice smith"), "alice-smith")

    def test_disallowed_characters_are_removed(self):
        self.assertEqual(normalize_handle("ali_ce+test"), "alicetest")

    def test_multiple_dashes_are_collapsed(self):
        self.assertEqual(normalize_handle("ali---ce"), "ali-ce")

    def test_edge_dashes_are_trimmed(self):
        self.assertEqual(normalize_handle("---alice---"), "alice")

    def test_nfkc_normalizes_full_width_ascii(self):
        self.assertEqual(normalize_handle("ＡＬＩＣＥ１２３"), "alice123")

    def test_non_latin_only_seed_becomes_empty(self):
        self.assertEqual(normalize_handle("علی"), "")

    def test_none_becomes_empty(self):
        self.assertEqual(normalize_handle(None), "")


class TruncateForSuffixTests(SimpleTestCase):
    def test_short_base_is_unchanged(self):
        self.assertEqual(_truncate_for_suffix("alice", 2), "alice")

    def test_long_base_reserves_suffix_room(self):
        value = _truncate_for_suffix("a" * 40, 3)
        self.assertEqual(value, "a" * 29)

    def test_truncation_removes_trailing_dash(self):
        base = ("a" * 28) + "-tail"
        self.assertEqual(_truncate_for_suffix(base, 3), "a" * 28)

    def test_empty_prefix_is_guarded(self):
        self.assertEqual(_truncate_for_suffix("---", 31), "")


class ReservedHandlesTests(SimpleTestCase):
    def test_reserved_handles_are_frozen(self):
        self.assertIsInstance(RESERVED_HANDLES, frozenset)

    def test_common_reserved_handles_are_present(self):
        self.assertTrue({"admin", "root", "support", "vorneq"} <= RESERVED_HANDLES)

    def test_all_reserved_handles_are_already_normalized(self):
        self.assertEqual(
            RESERVED_HANDLES,
            frozenset(normalize_handle(value) for value in RESERVED_HANDLES),
        )


class IntegrityClassifierTests(SimpleTestCase):
    @staticmethod
    def _postgres_error(constraint_name):
        cause = Exception("database error")
        cause.diag = SimpleNamespace(constraint_name=constraint_name)
        exc = IntegrityError("duplicate key")
        exc.__cause__ = cause
        return exc

    def test_extracts_postgres_constraint_name(self):
        exc = self._postgres_error("uniq_handle_per_identity_v1")
        self.assertEqual(
            _extract_violated_constraint(exc),
            "uniq_handle_per_identity_v1",
        )

    def test_extracts_sqlite_unique_columns(self):
        exc = IntegrityError(
            "UNIQUE constraint failed: core_identityhandle.identity_id"
        )
        self.assertEqual(
            _extract_violated_constraint(exc),
            "unique:core_identityhandle.identity_id",
        )

    def test_classifies_postgres_identity_constraint(self):
        exc = self._postgres_error("uniq_handle_per_identity_v1")
        self.assertTrue(_is_one_handle_per_identity_conflict(exc))
        self.assertFalse(_is_handle_uniqueness_conflict(exc))

    def test_classifies_postgres_handle_constraint_by_exact_name(self):
        exc = self._postgres_error("core_identityhandle_handle_key")
        self.assertTrue(_is_handle_uniqueness_conflict(exc))
        self.assertFalse(_is_one_handle_per_identity_conflict(exc))

    def test_similar_postgres_constraint_name_is_not_misclassified(self):
        exc = self._postgres_error("other_table_handle_key")
        self.assertFalse(_is_handle_uniqueness_conflict(exc))

    def test_classifies_sqlite_identity_constraint(self):
        exc = IntegrityError(
            "UNIQUE constraint failed: core_identityhandle.identity_id"
        )
        self.assertTrue(_is_one_handle_per_identity_conflict(exc))

    def test_classifies_sqlite_handle_constraint(self):
        exc = IntegrityError(
            "UNIQUE constraint failed: core_identityhandle.handle"
        )
        self.assertTrue(_is_handle_uniqueness_conflict(exc))

    def test_unrelated_integrity_error_is_not_classified(self):
        exc = IntegrityError("CHECK constraint failed: unrelated")
        self.assertFalse(_is_one_handle_per_identity_conflict(exc))
        self.assertFalse(_is_handle_uniqueness_conflict(exc))
