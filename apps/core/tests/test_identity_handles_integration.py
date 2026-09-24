from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import IntegrityError, close_old_connections, connection
from django.test import TestCase, TransactionTestCase

from apps.core.models import Identity, IdentityHandle
from apps.core.services.handles import (
    HandleAllocationError,
    reserve_handle_for_identity,
)


class IdentityHandleAllocationTests(TestCase):
    def make_identity(self, display_name="Alice"):
        return Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name=display_name,
        )

    def test_allocates_from_display_name_by_default(self):
        identity = self.make_identity("Alice Smith")
        handle = reserve_handle_for_identity(identity)
        self.assertEqual(handle.handle, "alice-smith")

    def test_display_address_is_derived(self):
        identity = self.make_identity()
        handle = reserve_handle_for_identity(identity, base_seed="alice")
        self.assertEqual(handle.display_address, "alice@vorneq.com")

    def test_stored_handle_has_no_domain(self):
        identity = self.make_identity()
        handle = reserve_handle_for_identity(identity, base_seed="alice")
        self.assertEqual(handle.handle, "alice")
        self.assertNotIn("@", handle.handle)

    def test_existing_handle_is_returned_idempotently(self):
        identity = self.make_identity()
        first = reserve_handle_for_identity(identity, base_seed="alice")
        second = reserve_handle_for_identity(identity, base_seed="different")
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(IdentityHandle.objects.filter(identity=identity).count(), 1)

    def test_reserved_word_is_transformed_after_normalization(self):
        identity = self.make_identity()
        handle = reserve_handle_for_identity(identity, base_seed="ADMIN")
        self.assertEqual(handle.handle, "admin-user")

    def test_dash_variant_is_not_an_exact_reserved_match(self):
        identity = self.make_identity()
        handle = reserve_handle_for_identity(identity, base_seed="A-D-M-I-N")
        self.assertEqual(handle.handle, "a-d-m-i-n")

    def test_handle_collision_retries_with_numeric_suffix(self):
        occupied = self.make_identity("Occupied")
        IdentityHandle.objects.create(identity=occupied, handle="ali")
        target = self.make_identity("Target")
        handle = reserve_handle_for_identity(target, base_seed="ali")
        self.assertEqual(handle.handle, "ali-2")

    def test_multiple_collisions_increment_suffix(self):
        for candidate in ("ali", "ali-2", "ali-3"):
            identity = self.make_identity(f"Occupied {candidate}")
            IdentityHandle.objects.create(identity=identity, handle=candidate)
        target = self.make_identity("Target")
        handle = reserve_handle_for_identity(target, base_seed="ali")
        self.assertEqual(handle.handle, "ali-4")

    def test_empty_normalization_uses_deterministic_fallback(self):
        identity = self.make_identity("علی")
        handle = reserve_handle_for_identity(identity, base_seed="علی")
        self.assertEqual(handle.handle, f"user-{identity.id.hex[:8]}")

    def test_empty_explicit_seed_does_not_fall_back_to_display_name(self):
        identity = self.make_identity("Alice")
        handle = reserve_handle_for_identity(identity, base_seed="")
        self.assertEqual(handle.handle, f"user-{identity.id.hex[:8]}")

    def test_long_base_is_truncated_to_max_length(self):
        identity = self.make_identity()
        handle = reserve_handle_for_identity(identity, base_seed="a" * 80)
        self.assertEqual(len(handle.handle), 32)
        self.assertEqual(handle.handle, "a" * 32)

    def test_long_base_leaves_room_for_collision_suffix(self):
        base = "a" * 80
        occupied = self.make_identity("Occupied")
        IdentityHandle.objects.create(identity=occupied, handle="a" * 32)
        target = self.make_identity("Target")
        handle = reserve_handle_for_identity(target, base_seed=base)
        self.assertEqual(len(handle.handle), 32)
        self.assertTrue(handle.handle.endswith("-2"))

    def test_database_enforces_one_handle_per_identity(self):
        identity = self.make_identity()
        IdentityHandle.objects.create(identity=identity, handle="alice")
        with self.assertRaises(IntegrityError):
            IdentityHandle.objects.create(identity=identity, handle="alice-2")

    def test_unrelated_integrity_error_is_propagated(self):
        identity = self.make_identity()
        unrelated = IntegrityError("CHECK constraint failed: unrelated")
        with patch.object(
            IdentityHandle.objects,
            "create",
            side_effect=unrelated,
        ):
            with self.assertRaises(IntegrityError) as caught:
                reserve_handle_for_identity(identity, base_seed="alice")
        self.assertIs(caught.exception, unrelated)

    def test_exhaustion_after_ten_candidates_raises(self):
        candidates = ["ali", *[f"ali-{number}" for number in range(2, 11)]]
        for candidate in candidates:
            occupied = self.make_identity(f"Occupied {candidate}")
            IdentityHandle.objects.create(identity=occupied, handle=candidate)

        target = self.make_identity("Target")
        with self.assertRaises(HandleAllocationError):
            reserve_handle_for_identity(target, base_seed="ali")
        self.assertFalse(IdentityHandle.objects.filter(identity=target).exists())


class IdentityHandleRaceTests(TransactionTestCase):
    def test_same_identity_concurrent_allocation_returns_one_row(self):
        if connection.vendor != "postgresql":
            self.skipTest("Race contract requires PostgreSQL.")

        identity = Identity.objects.create(
            kind=Identity.Kind.HUMAN,
            display_name="Concurrent",
        )
        identity_id = identity.pk
        barrier = Barrier(2)

        def allocate(seed):
            close_old_connections()
            try:
                worker_identity = Identity.objects.get(pk=identity_id)
                barrier.wait(timeout=10)
                result = reserve_handle_for_identity(
                    worker_identity,
                    base_seed=seed,
                )
                return result.pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(allocate, "concurrent-alpha"),
                executor.submit(allocate, "concurrent-beta"),
            ]
            result_ids = [future.result(timeout=20) for future in futures]

        rows = IdentityHandle.objects.filter(identity_id=identity_id)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(result_ids[0], result_ids[1])
        self.assertEqual(result_ids[0], rows.get().pk)
