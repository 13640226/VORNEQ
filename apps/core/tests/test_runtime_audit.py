"""The audit is observational, including its failure paths."""
from datetime import timedelta
from io import StringIO
import json
import os
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.db import DatabaseError, connections
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.core.management.commands import audit_runtime as audit


class IdentityTests(SimpleTestCase):
    @override_settings(VORNEQ_ENV="production", DEBUG=False)
    def test_wrong_sha_or_service_rejected_before_connection(self):
        with patch.dict(os.environ, {"RENDER_GIT_COMMIT": "a" * 40,
                                     "RENDER_SERVICE_ID": audit.TARGETS["production"][0]}):
            for sha, env in (("b" * 40, "production"), ("a" * 40, "staging"),
                             ("secret-not-a-sha", "production")):
                with self.assertRaisesMessage(CommandError, "INVALID_HOSTED_IDENTITY"):
                    audit.identity(env, sha, False)
            self.assertEqual(audit.identity("production", "a" * 40, False)["sha"], "a" * 40)
        with patch.dict(os.environ, {"RENDER_SERVICE_ID": "not-allowed",
                                     "RENDER_GIT_COMMIT": "a" * 40}):
            with self.assertRaises(CommandError):
                audit.identity("production", "a" * 40, False)

    @override_settings(VORNEQ_ENV="development")
    def test_local_rejects_hosted_markers(self):
        with patch.dict(os.environ, {"RENDER": "true"}):
            with self.assertRaisesMessage(CommandError, "INVALID_LOCAL_IDENTITY"):
                audit.identity(None, None, True)

    @override_settings(VORNEQ_ENV="staging", VORNEQ_AI_CHAT_FOLLOW_OWNER_DEPLOYMENTS=True,
                       VORNEQ_AI_IMAGE_FOLLOW_OWNER_DEPLOYMENTS=True,
                       VORNEQ_AI_EMERGENCY_STOP=False,
                       VORNEQ_AI_IMAGE_ENABLED=True, VORNEQ_AI_IMAGE_PAID_CALLS_ENABLED=True)
    def test_official_mode_does_not_call_network_bound_policies(self):
        with patch("apps.ai_core.views_global.global_ai_available",
                   side_effect=AssertionError("network-bound policy")), patch(
            "apps.ai_core.image_generation.policy.enabled",
            side_effect=AssertionError("network-bound policy")
        ), patch("apps.ai_core.image_generation.policy.paid_provider_enabled",
                 side_effect=AssertionError("network-bound policy")):
            result = audit.configuration("staging")
        self.assertEqual(result["effective_policy"]["chat"], audit.UNKNOWN)
        self.assertEqual(result["effective_policy"]["image_paid_web"], audit.UNKNOWN)

    @override_settings(VORNEQ_ENV="development", EMAIL_BACKEND="SECRET_EMAIL_BACKEND",
                       VORNEQ_AI_CHAT_BUDGET_MODEL="SECRET_MODEL")
    def test_configuration_never_echoes_arbitrary_strings(self):
        with patch.dict(os.environ, {"RESEND_API_KEY": "SECRET_RESEND",
                                     "OPENAI_API_KEY": "SECRET_OPENAI",
                                     "VORNEQ_AI_PHASE_B_MODEL": "SECRET_MODEL"}):
            data = audit.configuration("development")
        self.assertNotIn("SECRET_", json.dumps(data))
        self.assertTrue(data["resend_key_present"])
        self.assertEqual(data["email_backend"], "OTHER")

    @override_settings(VORNEQ_ENV="development")
    def test_safe_partial_error(self):
        out = StringIO()
        with patch.object(audit, "check_target"), patch.object(
            audit, "configuration", side_effect=RuntimeError("SECRET_DSN")
        ), patch.object(audit.Command, "read_section", return_value={"count": 0}):
            with self.assertRaisesMessage(CommandError, "AUDIT_INCOMPLETE"):
                call_command("audit_runtime", local_test=True, stdout=out)
        result = json.loads(out.getvalue())
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["errors"], ["configuration"])
        self.assertNotIn("SECRET_DSN", out.getvalue())


@override_settings(VORNEQ_ENV="development")
class ReadOnlyDatabaseTests(TransactionTestCase):
    databases = {"default", "ai_ledger"}

    def test_database_enforces_no_writes_and_restores_session(self):
        from django.contrib.auth.models import Group
        for alias in ("default", "ai_ledger"):
            conn = connections[alias]
            # Test a DDL write, without depending on tables on the ledger alias.
            with self.assertRaises(DatabaseError):
                with audit.readonly(alias, None, True) as ro:
                    with ro.cursor() as cur:
                        cur.execute("CREATE TABLE runtime_audit_forbidden (n integer)")
            self.assertNotIn("runtime_audit_forbidden", conn.introspection.table_names())
            self.assertTrue(conn.get_autocommit())
        # A normal test-only write still works after the audit exits.
        Group.objects.create(name="audit-restored")

    def test_nested_transactions_refused(self):
        from django.db import transaction
        with transaction.atomic():
            with self.assertRaisesMessage(CommandError, "NESTED_TRANSACTION_REFUSED"):
                with audit.readonly("default", None, True):
                    self.fail("nested audit must not run")

    def test_wrong_hosted_database_rejected_before_query(self):
        with self.assertRaisesMessage(CommandError, "INVALID_DATABASE_TARGET"):
            audit.check_target("default", "production", False)

    def test_full_report_and_redaction(self):
        from allauth.account.models import EmailAddress
        from apps.ai_core.models import AIChatJob, AIConversation, AIImageJob
        from apps.ai_ledger.models import BudgetAccount, BudgetReservation
        user = get_user_model().objects.create_user(
            username="private-audit-user", email="private-audit@example.invalid")
        EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
        conversation = AIConversation.objects.create(owner=user, title="PRIVATE_CONVERSATION")
        AIChatJob.objects.create(
            owner=user, conversation=conversation, request_id=uuid.uuid4(),
            fingerprint="a" * 64, status=AIChatJob.RUNNING, worker_id="private-worker-id",
            fencing_token=1, lease_until=timezone.now() - timedelta(seconds=5))
        AIImageJob.objects.create(owner=user, prompt="PRIVATE_PROMPT",
                                  prompt_digest="b" * 64, model_id="private-model",
                                  status=AIImageJob.STATUS_RUNNING, reservation_id=uuid.uuid4())
        account = BudgetAccount.objects.using("ai_ledger").create(
            ledger_id=uuid.uuid4(), total_allowance_micro=1000, safety_reserve_micro=100,
            reserved_micro=100, model_id="PRIVATE_LEDGER_MODEL",
            input_price_micro_per_mtok=1, output_price_micro_per_mtok=1)
        BudgetReservation.objects.using("ai_ledger").create(
            id=uuid.uuid4(), account=account, environment="staging", service_id="private-service",
            git_sha="c" * 40, actor_id=user.pk, reserved_micro=100, status="reserved")
        ledger_settings = dict(VORNEQ_AI_LEDGER_ENABLED=False,
                               VORNEQ_AI_LEDGER_ID=str(account.ledger_id),
                               VORNEQ_AI_IMAGE_LEDGER_ID=str(account.ledger_id),
                               VORNEQ_AI_LEDGER_DB_NAME=str(connections["ai_ledger"].settings_dict["NAME"]))
        out = StringIO()
        with override_settings(**ledger_settings):
            call_command("audit_runtime", local_test=True, stdout=out)
        report = json.loads(out.getvalue())
        self.assertEqual(report["status"], "COMPLETE")
        self.assertEqual(report["application"]["expired_chat_leases"], 1)
        self.assertEqual(report["application"]["image_running_with_reservation"], 1)
        self.assertEqual(report["application"]["identity"]["verified_primary_matching"], 1)
        self.assertTrue(report["application_migrations"]["ai_core_0005_applied"])
        self.assertEqual(report["ledger"]["chat"]["remaining_micro"], 800)
        self.assertEqual(report["ledger"]["chat"]["reservations"]["reserved"], 0)
        self.assertEqual(report["ledger"]["image"]["status"], "ACCOUNT_NOT_INDEPENDENT")
        self.assertFalse(report["configuration"]["ledger_configured"])
        # Inspect the ledger even while disabled; scope reservations to the environment.
        with override_settings(**ledger_settings), audit.readonly("ai_ledger", None, True) as conn:
            self.assertEqual(audit.ledger_db(conn, "staging")["chat"]["reservations"]["reserved"], 1)
            self.assertEqual(audit.ledger_db(conn, "production")["chat"]["reservations"]["reserved"], 0)
        for private in ("private-", "PRIVATE_", str(account.ledger_id), user.email):
            self.assertNotIn(private, out.getvalue())
        self.assertEqual(BudgetAccount.objects.using("ai_ledger").get(pk=account.pk).reserved_micro, 100)
        self.assertEqual(AIChatJob.objects.get().status, AIChatJob.RUNNING)
