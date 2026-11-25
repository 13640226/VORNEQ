"""V7-03.1a: dauerhafte Antwort-Jobs – Zustandsmaschine, Claim, Fencing, Queue, Ledger.

Offline, ohne bezahlte Aufrufe: Provider sind Fakes; die Ledger-Funktionen werden
gepatcht. Der echte Nebenläufigkeitstest läuft nur auf PostgreSQL.
"""
import threading
import uuid
from datetime import timedelta
from io import StringIO
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.ai_core import chat_jobs
from apps.ai_core.budgeted_provider import BudgetedProvider
from apps.ai_core.chat_jobs import (CapacityExceeded, InvalidTransition, JobsDisabled, Lease, RequestConflict,
                                    StaleLease, TRANSITIONS)
from apps.ai_core.conversations import context
from apps.ai_core.conversations.repository import ConversationNotFound
from apps.ai_core.models import AIChatJob as J, AIConversation, AIMessage
from apps.ai_core.providers.exceptions import ProviderTimeout, ProviderUnavailable
from apps.ai_core.providers.openai_responses import StreamOutcome
from apps.ai_core.tests.ledger_fakes import fake_reservation
from apps.ai_core.tests.test_v7_03_streaming import FakeStreamProvider

ON = dict(VORNEQ_ENV="development", VORNEQ_AI_CHAT_JOBS_ENABLED=True, VORNEQ_AI_EMERGENCY_STOP=False,
          VORNEQ_AI_CHAT_JOBS_MAX_ACTIVE_GLOBAL="", VORNEQ_AI_CHAT_JOBS_MAX_ACTIVE_PER_USER="")
QUESTION = "What is quantum computing?"


def make_user(prefix):
    return get_user_model().objects.create_user(username=f"{prefix}{uuid.uuid4().hex[:8]}",
                                                email=f"{prefix}@example.invalid", password="x-1!Aa-long")


class JobFixture:
    def setUp(self):
        super().setUp()
        self.user = make_user("j")
        self.other = make_user("k")
        self.conversation = AIConversation.objects.create(owner=self.user, language="en")

    def enqueue(self, request_id=None, question=QUESTION, user=None, conversation=None):
        return chat_jobs.enqueue(user or self.user, (conversation or self.conversation).id, question=question,
                                 language="en", request_id=request_id or uuid.uuid4())


@override_settings(**ON)
class StateMachineAndEnqueueTests(JobFixture, TestCase):
    def test_transition_table_terminal_states_are_final(self):
        for state in J.TERMINAL:
            self.assertEqual(TRANSITIONS[state], set())
        self.assertNotIn(J.RUNNING, TRANSITIONS[J.CANCEL_REQUESTED])     # kein Zurück
        self.assertNotIn(J.CANCELLED, TRANSITIONS[J.RUNNING])            # nur über CANCEL_REQUESTED
        self.assertNotIn(J.QUEUED, TRANSITIONS[J.CLAIMED])               # kein Auto-Retry
        self.assertEqual({s for s, _ in J.STATES}, set(TRANSITIONS))

    def test_enqueue_creates_one_job_and_messages_without_reservation(self):
        job, created = self.enqueue()
        self.assertTrue(created)
        self.assertEqual((job.status, job.ledger_state, job.reservation_id, job.fencing_token),
                         (J.QUEUED, J.LEDGER_NONE, None, 0))
        self.assertEqual(job.user_message.content, QUESTION)
        self.assertEqual(job.assistant_message.status, AIMessage.STATUS_PENDING)
        # Eigentümer-gebundene interne ID (uuid5), nie die rohe Client-ID.
        self.assertEqual(job.assistant_message.request_id, chat_jobs.message_request_id(self.user.pk, job.request_id))
        self.assertEqual(job.assistant_message.request_id.version, 5)

    def test_idempotent_replay_and_conflicts(self):
        rid = uuid.uuid4()
        first, _ = self.enqueue(rid)
        again, created = self.enqueue(rid)
        self.assertEqual((again.pk, created), (first.pk, False))
        self.assertEqual(AIMessage.objects.filter(conversation=self.conversation).count(), 2)
        with self.assertRaises(RequestConflict):
            self.enqueue(rid, question="different text")
        second_conv = AIConversation.objects.create(owner=self.user)
        with self.assertRaises(RequestConflict):
            self.enqueue(rid, conversation=second_conv)             # gleiche ID, andere Unterhaltung
        self.assertEqual(J.objects.count(), 1)

    def test_other_users_request_id_is_a_separate_namespace_without_oracle(self):
        rid = uuid.uuid4()
        mine, _ = self.enqueue(rid)
        other_conv = AIConversation.objects.create(owner=self.other)
        theirs, created = self.enqueue(rid, user=self.other, conversation=other_conv)
        # Gleiches Ergebnis wie für eine unbenutzte ID: neuer eigener Job, kein Konflikt.
        self.assertTrue(created)
        self.assertNotEqual(theirs.pk, mine.pk)
        self.assertEqual((theirs.owner_id, theirs.conversation_id), (self.other.pk, other_conv.id))
        self.assertNotEqual(theirs.assistant_message.request_id, mine.assistant_message.request_id)
        self.assertEqual(J.objects.filter(request_id=rid).count(), 2)

    def test_duplicate_after_completion_or_failure_returns_existing(self):
        for final in (J.COMPLETED, J.FAILED):
            with self.subTest(final=final):
                rid = uuid.uuid4()
                job, _ = self.enqueue(rid, question=f"{final}?")
                J.objects.filter(pk=job.pk).update(status=final)
                again, created = self.enqueue(rid, question=f"{final}?")
                self.assertEqual((again.pk, again.status, created), (job.pk, final, False))
        self.assertEqual(J.objects.count(), 2)

    def test_transaction_rollback_leaves_no_partial_rows(self):
        before = AIMessage.objects.count()
        with patch("apps.ai_core.models.AIChatJob.objects.create", side_effect=DatabaseError("x")), \
                self.assertRaises(DatabaseError):
            self.enqueue()
        self.assertEqual(AIMessage.objects.count(), before)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.message_count, 0)

    def test_flags_default_off_everywhere(self):
        from django.conf import settings as dj
        import importlib
        import os
        for name in ("VORNEQ_AI_CHAT_JOBS_ENABLED", "VORNEQ_AI_CHAT_JOBS_PRODUCTION_ENABLED",
                     "VORNEQ_AI_CHAT_STREAMING_ENABLED", "VORNEQ_AI_CHAT_STREAMING_PRODUCTION_ENABLED"):
            self.assertNotIn(name, os.environ)
        with override_settings(VORNEQ_AI_CHAT_JOBS_ENABLED=False, VORNEQ_AI_CHAT_JOBS_PRODUCTION_ENABLED=False):
            for env in ("development", "staging", "production"):
                with override_settings(VORNEQ_ENV=env):
                    self.assertFalse(chat_jobs.enabled())
                    self.assertIsNone(chat_jobs.claim("w"))

    def test_cross_user_conversation_and_gates(self):
        foreign = AIConversation.objects.create(owner=self.other)
        with self.assertRaises(ConversationNotFound):
            self.enqueue(conversation=foreign)
        with override_settings(VORNEQ_AI_CHAT_JOBS_ENABLED=False), self.assertRaises(JobsDisabled):
            self.enqueue()
        with override_settings(VORNEQ_ENV="production", VORNEQ_AI_CHAT_JOBS_ENABLED=True), \
                self.assertRaises(JobsDisabled):
            self.enqueue()
        with self.assertRaises(chat_jobs.ChatJobError):
            chat_jobs.enqueue(self.user, self.conversation.id, question=QUESTION, language="en",
                              request_id=uuid.UUID(int=1))     # kein UUIDv4
        self.assertFalse(J.objects.exists())

    def test_capacity_per_user_and_global_from_configuration(self):
        with override_settings(VORNEQ_AI_CHAT_JOBS_MAX_ACTIVE_PER_USER="2"):
            self.enqueue()
            self.enqueue()
            with self.assertRaises(CapacityExceeded) as ctx:
                self.enqueue()
            self.assertEqual(ctx.exception.code, "user_capacity_exceeded")
        with override_settings(VORNEQ_AI_CHAT_JOBS_MAX_ACTIVE_GLOBAL="2", VORNEQ_AI_CHAT_JOBS_MAX_ACTIVE_PER_USER="9"):
            conv = AIConversation.objects.create(owner=self.other)
            with self.assertRaises(CapacityExceeded) as ctx:
                self.enqueue(user=self.other, conversation=conv)
            self.assertEqual(ctx.exception.code, "global_capacity_exceeded")
        J.objects.update(status=J.COMPLETED)            # beendete Jobs zählen nicht
        self.enqueue()
        for raw, expected in (("0", 32), ("abc", 32), ("-1", 32), ("7", 7), (12, 12)):
            with self.subTest(raw=raw), override_settings(VORNEQ_AI_CHAT_JOBS_MAX_ACTIVE_GLOBAL=raw):
                self.assertEqual(chat_jobs.max_active_global(), expected)

    def test_redis_failure_on_wakeup_is_logged_and_job_is_durable(self):
        with patch("django.core.cache.cache.set", side_effect=ConnectionError("redis down")), \
                self.assertLogs("apps.ai_core.chat_jobs", "WARNING") as logs:
            job, created = self.enqueue()
        self.assertTrue(created)
        self.assertTrue(J.objects.filter(pk=job.pk, status=J.QUEUED).exists())
        self.assertIn("ai_chat_job_wakeup_unavailable kind=ConnectionError", logs.output[0])


@override_settings(**ON)
class ClaimLeaseFencingTests(JobFixture, TestCase):
    def test_claim_oldest_once_with_token_and_lease(self):
        first, _ = self.enqueue()
        second, _ = self.enqueue(question="second?")
        a = chat_jobs.claim("worker-a")
        b = chat_jobs.claim("worker-b")
        self.assertEqual((a.job_id, b.job_id), (first.pk, second.pk))
        self.assertIsNone(chat_jobs.claim("worker-c"))
        job = J.objects.get(pk=a.job_id)
        self.assertEqual((job.status, job.worker_id, job.fencing_token, job.attempts), (J.CLAIMED, "worker-a", 1, 1))
        self.assertGreater(job.lease_until, timezone.now())
        with self.assertRaises(chat_jobs.ChatJobError):
            chat_jobs.claim("")

    def test_heartbeat_and_lease_expiration(self):
        self.enqueue()
        lease = chat_jobs.claim("w")
        before = J.objects.get(pk=lease.job_id).lease_until
        self.assertEqual(chat_jobs.heartbeat(lease, now=timezone.now() + timedelta(seconds=5)), J.CLAIMED)
        self.assertGreater(J.objects.get(pk=lease.job_id).lease_until, before)
        later = timezone.now() + timedelta(seconds=chat_jobs.lease_seconds() + 60)
        with self.assertRaises(StaleLease):
            chat_jobs.heartbeat(lease, now=later)
        with self.assertRaises(StaleLease):
            chat_jobs.transition(lease, J.RUNNING, now=later)

    def test_stale_worker_cannot_write_after_reclaim(self):
        self.enqueue()
        old = chat_jobs.claim("old")
        # Simulierter Reaper (V7-03.1c) für einen nachweislich nicht gesendeten Claim.
        J.objects.filter(pk=old.job_id).update(status=J.QUEUED, lease_until=None, worker_id="")
        new = chat_jobs.claim("new")
        self.assertEqual((new.job_id, new.token), (old.job_id, 2))
        for action in (lambda: chat_jobs.heartbeat(old), lambda: chat_jobs.transition(old, J.RUNNING),
                       lambda: chat_jobs.bind_ledger(old, ledger_state=J.LEDGER_UNCERTAIN)):
            with self.assertRaises(StaleLease):
                action()
        forged = Lease(old.job_id, "new", 1)              # richtiger Worker, alter Token
        with self.assertRaises(StaleLease):
            chat_jobs.heartbeat(forged)
        chat_jobs.transition(new, J.RUNNING)
        with self.assertRaises(StaleLease):
            chat_jobs.checkpoint(old, "evil", 99)
        self.assertEqual(chat_jobs.checkpoint(new, "good", 1), J.RUNNING)
        job = J.objects.get(pk=new.job_id)
        self.assertEqual((job.status, job.worker_id, job.ledger_state, job.assistant_message.content),
                         (J.RUNNING, "new", J.LEDGER_NONE, "good"))

    def test_transition_validation_and_terminal_closes_lease(self):
        self.enqueue()
        lease = chat_jobs.claim("w")
        with self.assertRaises(InvalidTransition):
            chat_jobs.transition(lease, J.COMPLETED)        # CLAIMED -> COMPLETED nicht erlaubt
        chat_jobs.transition(lease, J.RUNNING)
        chat_jobs.transition(lease, J.FAILED, error_code="x")
        job = J.objects.get(pk=lease.job_id)
        self.assertEqual((job.status, job.lease_until), (J.FAILED, None))
        self.assertIsNotNone(job.finished_at)
        with self.assertRaises(StaleLease):
            chat_jobs.heartbeat(lease)                      # Terminal: keine Lease mehr

    def test_checkpoint_monotonic_and_never_completed_or_in_context(self):
        self.enqueue()
        lease = chat_jobs.claim("w")
        chat_jobs.transition(lease, J.RUNNING)
        chat_jobs.checkpoint(lease, "alpha beta", 2)
        chat_jobs.checkpoint(lease, "alpha", 1)              # älter: ignoriert
        job = J.objects.get(pk=lease.job_id)
        self.assertEqual((job.checkpoint_sequence, job.checkpoint_chars), (2, len("alpha beta")))
        message = job.assistant_message
        self.assertEqual((message.status, message.content), (AIMessage.STATUS_PENDING, "alpha beta"))
        self.assertEqual(context.prior_turns(self.conversation, question="next"), ())

    def test_cancel_semantics_and_isolation(self):
        queued, _ = self.enqueue()
        self.assertEqual(chat_jobs.request_cancel(self.user, queued.pk), J.CANCELLED)
        self.assertEqual(AIMessage.objects.get(pk=queued.assistant_message_id).error_code, "cancelled")
        running_job, _ = self.enqueue(question="second")
        lease = chat_jobs.claim("w")
        chat_jobs.transition(lease, J.RUNNING)
        self.assertIsNone(chat_jobs.request_cancel(self.other, running_job.pk))         # fremd
        self.assertEqual(chat_jobs.request_cancel(self.user, running_job.pk), J.CANCEL_REQUESTED)
        self.assertEqual(chat_jobs.request_cancel(self.user, running_job.pk), J.CANCEL_REQUESTED)  # idempotent
        self.assertEqual(chat_jobs.checkpoint(lease, "x", 1), J.CANCEL_REQUESTED)
        self.assertEqual(chat_jobs.request_cancel(self.user, queued.pk), J.CANCELLED)  # terminal unverändert


@override_settings(**ON)
class RunAndLedgerTests(JobFixture, TestCase):
    def claimed(self, question=QUESTION):
        self.enqueue(question=question)
        return chat_jobs.claim("w")

    def run_with(self, lease, inner, *, budgeted=True, reserve=None, settle_state="finalized"):
        reservation = fake_reservation()
        factory = (lambda job, turns: BudgetedProvider(inner, actor_id=job.owner_id)) if budgeted else \
            (lambda job, turns: inner)
        settle_value = None if settle_state == "unacknowledged" else settle_state
        with patch("apps.ai_core.budgeted_provider.ledger.reserve",
                   **({"side_effect": reserve} if reserve else {"return_value": reservation})) as res, \
                patch("apps.ai_core.budgeted_provider.ledger.settle", return_value=settle_value) as settle, \
                patch("apps.ai_core.budgeted_provider.ledger.release", return_value="released") as release:
            status = chat_jobs.run_claimed(lease, provider_factory=factory)
        return status, reservation, res, settle, release

    def test_completed_binds_reservation_and_finalized_ledger_state(self):
        lease = self.claimed()
        inner = FakeStreamProvider(["Quantum ", "computing."])
        status, reservation, reserve, settle, _ = self.run_with(lease, inner)
        job = J.objects.get(pk=lease.job_id)
        self.assertEqual(status, J.COMPLETED)
        self.assertEqual((job.status, job.ledger_state, job.reservation_id, job.provider_request_sent),
                         (J.COMPLETED, J.LEDGER_FINALIZED, reservation.id, True))
        self.assertEqual(reserve.call_count, 1)
        self.assertEqual(settle.call_args.kwargs["usage"], (120, 340))
        message = job.assistant_message
        self.assertEqual((message.status, message.content, message.ledger_reservation_id),
                         (AIMessage.STATUS_COMPLETED, "Quantum computing.", reservation.id))
        self.assertEqual(inner.calls, 1)
        self.assertIsNone(chat_jobs.claim("w2"))           # kein zweiter Lauf, keine zweite Reservierung

    def test_unknown_usage_cancel_timeout_limit_and_unacknowledged(self):
        cases = [
            ("cancel", J.CANCELLED, J.LEDGER_UNCERTAIN, "uncertain"),
            ("timeout", J.UNCERTAIN, J.LEDGER_UNCERTAIN, "uncertain"),
            ("limit", J.INCOMPLETE, J.LEDGER_FINALIZED, "finalized"),
            ("unacked", J.COMPLETED, J.LEDGER_UNACKNOWLEDGED, "unacknowledged"),
        ]
        for name, job_status, ledger_state, settle_state in cases:
            with self.subTest(name):
                lease = self.claimed(question=f"{name} question?")
                job_id = lease.job_id
                if name == "cancel":
                    inner = FakeStreamProvider(["a" * 2100, "b" * 2100, "c"],
                                               on_step=lambda i, uid=self.user, jid=job_id:
                                               i == 1 and chat_jobs.request_cancel(uid, jid))
                elif name == "timeout":
                    inner = FakeStreamProvider(["a", "b"], raise_at=1, exc=ProviderTimeout("t"))
                elif name == "limit":
                    inner = FakeStreamProvider(["a"], final=StreamOutcome("incomplete", "max_output_tokens", (1, 2)))
                else:
                    inner = FakeStreamProvider(["ok"])
                status, *_ = self.run_with(lease, inner, settle_state=settle_state)
                job = J.objects.get(pk=job_id)
                self.assertEqual((status, job.status, job.ledger_state), (job_status, job_status, ledger_state))
                self.assertNotEqual(job.assistant_message.status, AIMessage.STATUS_COMPLETED
                                    if job_status != J.COMPLETED else "x")

    def test_ledger_failure_means_no_provider_call(self):
        from apps.ai_ledger.service import LedgerUnavailable
        lease = self.claimed()
        inner = FakeStreamProvider(["never"])
        status, *_ = self.run_with(lease, inner, reserve=LedgerUnavailable("down"))
        job = J.objects.get(pk=lease.job_id)
        # Nichts reserviert; die vorab vermerkte Korrelations-ID bleibt für die Reconciliation.
        self.assertEqual((status, job.ledger_state), (J.FAILED, J.LEDGER_NONE))
        self.assertIsNotNone(job.reservation_id)
        self.assertEqual(inner.calls, 0)

    def test_reservation_crash_window_correlation_id_is_durable_before_reserve(self):
        lease = self.claimed()
        seen = {}

        def reserve(**kwargs):
            job = J.objects.get(pk=lease.job_id)       # Zustand im Moment der Reservierung
            seen.update(passed=kwargs.get("reservation_id"), stored=job.reservation_id, state=job.ledger_state)
            raise KeyboardInterrupt("worker crash right after reserve")
        with self.assertRaises(KeyboardInterrupt):
            self.run_with(lease, FakeStreamProvider(["x"]), reserve=reserve)
        self.assertIsNotNone(seen["passed"])
        self.assertEqual((seen["stored"], seen["state"]), (seen["passed"], J.LEDGER_RESERVING))
        job = J.objects.get(pk=lease.job_id)
        self.assertEqual((job.reservation_id, job.ledger_state, job.status),
                         (seen["passed"], J.LEDGER_RESERVING, J.RUNNING))   # auffindbar, nicht erneut gestartet
        self.assertIsNone(chat_jobs.claim("other"))

    def test_known_usage_after_lease_loss_is_still_settled(self):
        lease = self.claimed()

        def steal(index):
            if index == 1:
                J.objects.filter(pk=lease.job_id).update(lease_until=timezone.now() - timedelta(seconds=1))
        inner = FakeStreamProvider(["a" * 2100, "b" * 2100, "c"], on_step=steal)
        with self.assertLogs("apps.ai_core.chat_jobs", "WARNING") as logs:
            status, reservation, _res, settle, _rel = self.run_with(lease, inner, settle_state="finalized")
        self.assertIsNone(status)
        self.assertEqual(settle.call_count, 1)
        self.assertEqual(settle.call_args.kwargs["usage"], None)     # Stream wurde vor Usage beendet
        self.assertIn(f"reservation={reservation.id}", "\n".join(logs.output))
        job = J.objects.get(pk=lease.job_id)
        self.assertEqual(job.ledger_state, J.LEDGER_RESERVED)           # fencing: keine Überschreibung

    def test_not_sent_is_released(self):
        lease = self.claimed()
        inner = FakeStreamProvider([], raise_at=-1, exc=ProviderUnavailable("no key"))
        status, _reservation, _res, settle, release = self.run_with(lease, inner)
        job = J.objects.get(pk=lease.job_id)
        self.assertEqual((status, job.ledger_state, job.provider_request_sent), (J.FAILED, J.LEDGER_RELEASED, False))
        release.assert_called_once()
        settle.assert_not_called()

    def test_budget_refusal_and_emergency_stop_before_call(self):
        from apps.ai_core.engine.budget import BudgetExceeded
        lease = self.claimed()

        def refuse(job, turns):
            raise BudgetExceeded("over")
        self.assertEqual(chat_jobs.run_claimed(lease, provider_factory=refuse), J.FAILED)
        self.assertEqual(J.objects.get(pk=lease.job_id).error_code, "rate_limited")
        lease = self.claimed(question="second?")
        inner = FakeStreamProvider(["x"])
        with patch("apps.ai_ledger.service.emergency_stop_active", return_value=True):
            status = chat_jobs.run_claimed(lease, provider_factory=lambda job, turns: inner)
        self.assertEqual((status, inner.calls), (J.FAILED, 0))

    def test_emergency_stop_during_run(self):
        lease = self.claimed()
        inner = FakeStreamProvider(["a" * 2100, "b"])
        with patch("apps.ai_ledger.service.emergency_stop_active", side_effect=[False, True, True]):
            status, *_ = self.run_with(lease, inner, settle_state="uncertain")
        job = J.objects.get(pk=lease.job_id)
        self.assertEqual((status, job.error_code), (J.INCOMPLETE, "emergency_stop"))

    def test_emergency_stop_before_claim_and_cancellation_still_allowed(self):
        job, _ = self.enqueue()
        with patch("apps.ai_ledger.service.emergency_stop_active", return_value=True):
            self.assertIsNone(chat_jobs.claim("w"))
            self.assertEqual(chat_jobs.request_cancel(self.user, job.pk), J.CANCELLED)
        self.assertEqual(J.objects.get(pk=job.pk).attempts, 0)

    def test_cancel_before_run_sends_nothing(self):
        queued, _ = self.enqueue()
        lease = chat_jobs.claim("w")
        self.assertEqual(chat_jobs.request_cancel(self.user, queued.pk), J.CANCEL_REQUESTED)
        inner = FakeStreamProvider(["never"])
        status, _r, reserve, *_ = self.run_with(lease, inner)
        self.assertEqual((status, inner.calls, reserve.call_count), (J.CANCELLED, 0, 0))

    def test_lease_lost_mid_run_does_not_finalize(self):
        lease = self.claimed()

        def steal(index):
            if index == 1:
                J.objects.filter(pk=lease.job_id).update(fencing_token=99, worker_id="thief")
        inner = FakeStreamProvider(["a" * 2100, "b" * 2100, "c"], on_step=steal)
        with self.assertLogs("apps.ai_core.chat_jobs", "WARNING"):
            status, _r, _res, settle, _rel = self.run_with(lease, inner, settle_state="uncertain")
        job = J.objects.get(pk=lease.job_id)
        self.assertIsNone(status)
        self.assertEqual((job.status, job.worker_id), (J.RUNNING, "thief"))
        self.assertEqual(job.assistant_message.status, AIMessage.STATUS_PENDING)
        self.assertEqual(settle.call_count, 1)             # Ledger trotzdem genau einmal abgerechnet

    def test_finish_database_failure_is_logged_job_stays_active(self):
        lease = self.claimed()
        with patch("apps.ai_core.conversations.service.complete_turn", side_effect=DatabaseError("pg down")), \
                self.assertLogs("apps.ai_core.chat_jobs", "ERROR") as logs:
            status, *_ = self.run_with(lease, FakeStreamProvider(["ok"]))
        self.assertIsNone(status)
        self.assertIn("ai_chat_job_finish_failed", logs.output[0])
        self.assertNotIn("pg down", logs.output[0])
        self.assertEqual(J.objects.get(pk=lease.job_id).status, J.RUNNING)


@override_settings(**ON)
class WorkerCommandTests(JobFixture, TestCase):
    def test_gate_and_single_job(self):
        with override_settings(VORNEQ_AI_CHAT_JOBS_ENABLED=False), self.assertRaises(CommandError):
            call_command("run_chat_jobs", stdout=StringIO())
        self.enqueue()
        out = StringIO()
        with patch("apps.ai_core.chat_jobs.run_claimed", return_value=J.COMPLETED) as run:
            call_command("run_chat_jobs", stdout=out)
        self.assertEqual(run.call_count, 1)
        self.assertIn("CHAT_JOBS_DONE processed=1", out.getvalue())

    def test_postgres_failure_on_claim(self):
        with patch("apps.ai_core.chat_jobs.claim", side_effect=DatabaseError("x")), \
                self.assertRaises(CommandError):
            call_command("run_chat_jobs", stdout=StringIO(), stderr=StringIO())


class MigrationTests(TransactionTestCase):
    def test_forward_and_reverse(self):
        executor = MigrationExecutor(connection)
        executor.migrate([("ai_core", "0004_image_generation_job_v1")])
        self.assertNotIn("ai_core_aichatjob", connection.introspection.table_names())
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([("ai_core", "0005_chat_job_v1")])
        self.assertIn("ai_core_aichatjob", connection.introspection.table_names())


@skipUnless(connection.vendor == "postgresql", "echte Nebenläufigkeit nur auf PostgreSQL")
@override_settings(**ON)
class PostgresConcurrencyTests(TransactionTestCase):
    def _threads(self, target, count):
        barrier = threading.Barrier(count)
        results, errors = [], []

        def run():
            try:
                barrier.wait(timeout=10)
                results.append(target())
            except Exception as exc:  # noqa: BLE001 – Ergebnis wird geprüft
                errors.append(exc)
            finally:
                connections.close_all()
        threads = [threading.Thread(target=run) for _ in range(count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        return results, errors

    def test_concurrent_claims_never_double_claim(self):
        user = make_user("c")
        conversation = AIConversation.objects.create(owner=user)
        with override_settings(VORNEQ_AI_CHAT_JOBS_MAX_ACTIVE_PER_USER="50"):
            ids = {chat_jobs.enqueue(user, conversation.id, question=f"q{i}?", language="en",
                                     request_id=uuid.uuid4())[0].pk for i in range(6)}
        results, errors = self._threads(lambda: chat_jobs.claim(f"w-{threading.get_ident()}"), 10)
        self.assertEqual(errors, [])
        leases = [r for r in results if r is not None]
        self.assertEqual(len(leases), 6)
        self.assertEqual({lease.job_id for lease in leases}, ids)
        self.assertEqual(J.objects.filter(status=J.CLAIMED, fencing_token=1).count(), 6)

    def test_concurrent_enqueue_respects_capacity_and_idempotency(self):
        user = make_user("d")
        conversation = AIConversation.objects.create(owner=user)
        with override_settings(VORNEQ_AI_CHAT_JOBS_MAX_ACTIVE_PER_USER="3"):
            results, errors = self._threads(
                lambda: chat_jobs.enqueue(user, conversation.id, question="same?", language="en",
                                          request_id=uuid.uuid4()), 8)
        self.assertEqual(len(results), 3)
        self.assertEqual(len(errors), 5)
        self.assertTrue(all(isinstance(e, CapacityExceeded) for e in errors), errors)
        self.assertEqual(J.objects.filter(owner=user).count(), 3)
        rid = uuid.uuid4()
        J.objects.update(status=J.COMPLETED)
        results, errors = self._threads(
            lambda: chat_jobs.enqueue(user, conversation.id, question="dup?", language="en", request_id=rid), 6)
        self.assertEqual(errors, [])
        self.assertEqual(sum(1 for _job, created in results if created), 1)
        self.assertEqual(J.objects.filter(request_id=rid).count(), 1)
        self.assertEqual(AIMessage.objects.filter(request_id=chat_jobs.message_request_id(user.pk, rid)).count(), 1)

    def test_concurrent_cancellation_is_consistent(self):
        user = make_user("f")
        conversation = AIConversation.objects.create(owner=user)
        job, _ = chat_jobs.enqueue(user, conversation.id, question="c?", language="en", request_id=uuid.uuid4())
        lease = chat_jobs.claim("w")
        chat_jobs.transition(lease, J.RUNNING)
        results, errors = self._threads(lambda: chat_jobs.request_cancel(user, job.pk), 6)
        self.assertEqual(errors, [])
        self.assertEqual(set(results), {J.CANCEL_REQUESTED})
        self.assertEqual(J.objects.get(pk=job.pk).status, J.CANCEL_REQUESTED)

    def test_concurrent_heartbeat_and_stale_finalization(self):
        user = make_user("e")
        conversation = AIConversation.objects.create(owner=user)
        chat_jobs.enqueue(user, conversation.id, question="hb?", language="en", request_id=uuid.uuid4())
        lease = chat_jobs.claim("w")
        chat_jobs.transition(lease, J.RUNNING)
        results, errors = self._threads(lambda: chat_jobs.heartbeat(lease), 5)
        self.assertEqual((len(results), errors), (5, []))
        J.objects.filter(pk=lease.job_id).update(fencing_token=7)
        results, errors = self._threads(lambda: chat_jobs.transition(lease, J.COMPLETED), 4)
        self.assertTrue(all(isinstance(e, StaleLease) for e in errors) and len(errors) == 4)
        self.assertEqual(J.objects.get(pk=lease.job_id).status, J.RUNNING)


@skipUnless(connection.vendor == "postgresql", "echter Ledger auf PostgreSQL")
class LedgerCorrelationPostgresTests(TransactionTestCase):
    """Reservierung mit vorab vermerkter ID und parallele Abrechnung im echten Ledger."""
    databases = {"default", "ai_ledger"}

    def setUp(self):
        from apps.ai_ledger.tests import helpers as h
        self.h = h
        override = override_settings(**h.ledger_settings())
        override.enable()
        self.addCleanup(override.disable)
        h.provision(10)

    def reserve(self, reservation_id):
        from apps.ai_ledger.service import LEDGER_ALIAS, LedgerConfig, reserve_with_config
        config = LedgerConfig(self.h.LEDGER_ID, connections[LEDGER_ALIAS].settings_dict["NAME"])
        return reserve_with_config(config, environment="production",
                                   service_id=self.h.runtime("production")["RENDER_SERVICE_ID"],
                                   git_sha=self.h.SHA, actor_id=7, model=self.h.MODEL,
                                   input_bytes=self.h.INPUT_BYTES, max_output_tokens=self.h.MAX_OUT,
                                   reservation_id=reservation_id)

    def test_explicit_id_is_used_and_duplicates_fail_closed(self):
        from apps.ai_ledger.models import BudgetAccount, BudgetReservation
        from apps.ai_ledger.service import LEDGER_ALIAS, LedgerUnavailable
        rid = uuid.uuid4()
        reservation = self.reserve(rid)
        self.assertEqual(reservation.id, rid)
        reserved_before = BudgetAccount.objects.using(LEDGER_ALIAS).get(ledger_id=self.h.LEDGER_ID).reserved_micro
        with self.assertRaises(LedgerUnavailable):
            self.reserve(rid)                                 # gleiche ID: kein zweiter Betrag
        self.assertEqual(BudgetAccount.objects.using(LEDGER_ALIAS).get(ledger_id=self.h.LEDGER_ID).reserved_micro,
                         reserved_before)
        self.assertEqual(BudgetReservation.objects.using(LEDGER_ALIAS).filter(id=rid).count(), 1)
        with self.assertRaises(LedgerUnavailable):
            self.reserve(uuid.uuid1())                        # nur UUIDv4

    def test_concurrent_settlement_is_acknowledged_exactly_once(self):
        from apps.ai_ledger.models import BudgetReservation
        from apps.ai_ledger.service import LEDGER_ALIAS, settle
        reservation = self.reserve(uuid.uuid4())
        barrier = threading.Barrier(6)
        acks = []

        def worker(i):
            try:
                barrier.wait(timeout=10)
                acks.append(settle(reservation, usage=(100, 50) if i % 2 else None, outcome="race"))
            finally:
                connections.close_all()
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        self.assertEqual(len([a for a in acks if a is not None]), 1)
        row = BudgetReservation.objects.using(LEDGER_ALIAS).get(id=reservation.id)
        self.assertIn(row.status, ("finalized", "uncertain"))
        if row.status == "uncertain":
            self.assertIsNone(row.observed_micro)             # unbekannte Kosten nie 0
