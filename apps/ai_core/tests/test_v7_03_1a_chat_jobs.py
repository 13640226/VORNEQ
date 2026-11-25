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
        self.assertEqual(job.assistant_message.request_id, job.request_id)

    def test_idempotent_replay_and_conflicts(self):
        rid = uuid.uuid4()
        first, _ = self.enqueue(rid)
        again, created = self.enqueue(rid)
        self.assertEqual((again.pk, created), (first.pk, False))
        self.assertEqual(AIMessage.objects.filter(conversation=self.conversation).count(), 2)
        with self.assertRaises(RequestConflict):
            self.enqueue(rid, question="different text")
        other_conv = AIConversation.objects.create(owner=self.other)
        with self.assertRaises(RequestConflict):
            self.enqueue(rid, user=self.other, conversation=other_conv)
        self.assertEqual(J.objects.count(), 1)

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
        self.assertEqual((status, job.ledger_state, job.reservation_id), (J.FAILED, J.LEDGER_NONE, None))
        self.assertEqual(inner.calls, 0)

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
        self.assertEqual(AIMessage.objects.filter(request_id=rid).count(), 1)

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
