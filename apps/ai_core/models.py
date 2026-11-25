"""Isolated Staging AI reservation ledger, default-off and never for Production.

Reservation records are durable budget allowances, not actual OpenAI invoices.
They are deliberately never refunded automatically on errors/timeouts.
"""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class StagingAIBudgetDay(models.Model):
    day_utc = models.DateField(unique=True)
    reserved_micro_usd = models.PositiveIntegerField(default=0)
    request_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(reserved_micro_usd__gte=0),
                name="ai_staging_budget_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(request_count__gte=0),
                name="ai_staging_requests_nonnegative",
            ),
        ]


class AIChatRequestGuard(models.Model):
    """Durable idempotency authority for Staging AI chat.

    Stores only a random request identifier and HMAC/fingerprint metadata.
    No question, session token, answer, or provider credentials are persisted.
    Rows must not be automatically removed while the identifier could be reused:
    deletion would reopen the duplicate-provider window.
    """

    request_id = models.UUIDField(primary_key=True, editable=False)
    actor_id = models.BigIntegerField()
    session_digest = models.CharField(max_length=64)
    fingerprint = models.CharField(max_length=64)
    state = models.CharField(
        max_length=10,
        choices=[("running", "running"), ("finished", "finished")],
        default="running",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_at"], name="ai_chat_guard_created_idx"),
        ]


class AIConversation(models.Model):
    """Persistent AI conversation owned by exactly one user (design V1, D1-D5).

    Every query MUST be owner-bound (see conversations.repository). Deleting a
    conversation moves it to a 30-day trash (D2); ``ai_conversations_purge``
    removes it permanently afterwards. Content is never logged or registered
    in Django admin.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name="ai_conversations")
    title = models.CharField(max_length=120)
    language = models.CharField(max_length=2, default="fa")
    message_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(default=timezone.now)
    archived_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["owner", "deleted_at", "archived_at", "last_message_at"],
                         name="ai_conv_owner_list_idx"),
            models.Index(fields=["deleted_at"], name="ai_conv_deleted_idx"),
        ]


class AIMessage(models.Model):
    """One turn of a conversation. Only user/assistant roles are ever stored:
    instructions stay in code so stored text can never become an instruction."""

    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    # Durable request state of the assistant turn (design V1, section 11):
    # pending   = request accepted and durably recorded BEFORE any provider call
    # completed / insufficient_evidence / failed = final, committed together with
    #             the request guard transition in ONE PostgreSQL transaction
    # uncertain = provider outcome unknown (timeout, interruption, persistence
    #             failure after the provider call); never retried automatically
    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_INSUFFICIENT = "insufficient_evidence"
    STATUS_FAILED = "failed"
    STATUS_UNCERTAIN = "uncertain"
    FINAL_STATUSES = (STATUS_COMPLETED, STATUS_INSUFFICIENT, STATUS_FAILED, STATUS_UNCERTAIN)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="messages")
    sequence = models.PositiveIntegerField()
    role = models.CharField(max_length=10, choices=[(ROLE_USER, ROLE_USER), (ROLE_ASSISTANT, ROLE_ASSISTANT)])
    content = models.TextField(blank=True, default="")
    status = models.CharField(max_length=24, default=STATUS_COMPLETED, choices=[
        (STATUS_PENDING, STATUS_PENDING), (STATUS_COMPLETED, STATUS_COMPLETED),
        (STATUS_INSUFFICIENT, STATUS_INSUFFICIENT), (STATUS_FAILED, STATUS_FAILED),
        (STATUS_UNCERTAIN, STATUS_UNCERTAIN)])
    error_code = models.CharField(max_length=40, blank=True, default="")
    citations = models.JSONField(default=list, blank=True)
    # Unique per assistant turn: replaying a request ID can never store twice.
    request_id = models.UUIDField(null=True, blank=True, unique=True)
    ledger_reservation_id = models.UUIDField(null=True, blank=True)
    model = models.CharField(max_length=100, blank=True, default="")
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["conversation", "sequence"], name="ai_msg_conv_seq_unique"),
            models.CheckConstraint(condition=Q(role__in=["user", "assistant"]), name="ai_msg_role_valid"),
            models.CheckConstraint(
                condition=Q(status__in=["pending", "completed", "insufficient_evidence", "failed", "uncertain"]),
                name="ai_msg_status_valid"),
            # Only assistant turns carry a request ID or a pending/uncertain state.
            models.CheckConstraint(condition=Q(role="assistant") | Q(request_id__isnull=True, status="completed"),
                                   name="ai_msg_user_turn_plain"),
        ]
        indexes = [
            models.Index(fields=["conversation", "sequence"], name="ai_msg_conv_seq_idx"),
            models.Index(fields=["status", "created_at"], name="ai_msg_status_time_idx"),
        ]
        ordering = ["sequence"]


class AIImageJob(models.Model):
    """Persistent, owner-bound request. Running work is NEVER auto-retried.

    The prompt is erased after terminal completion. No public media URL.
    A repeated client UUID returns the existing job instead of a new charge.
    """
    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_UNCERTAIN = "uncertain"
    STATES = [(x, x) for x in (
        STATUS_QUEUED, STATUS_RUNNING, STATUS_COMPLETED,
        STATUS_FAILED, STATUS_UNCERTAIN,
    )]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="ai_image_jobs",
    )
    prompt = models.TextField(max_length=2000)
    prompt_digest = models.CharField(max_length=64)
    model_id = models.CharField(max_length=100)
    image_size = models.CharField(max_length=16, default="1024x1024")
    provider = models.CharField(max_length=10, default="mock")
    status = models.CharField(max_length=12, choices=STATES, default=STATUS_QUEUED)
    reservation_id = models.UUIDField(null=True, blank=True)
    storage_key = models.CharField(max_length=255, blank=True)
    image_digest = models.CharField(max_length=64, blank=True)
    is_mock = models.BooleanField(default=False)
    error_code = models.CharField(max_length=40, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["owner", "created_at"], name="ai_image_owner_day_idx"),
            models.Index(fields=["status", "created_at"], name="ai_image_queue_idx"),
        ]


class AIImageDailyQuota(models.Model):
    """Global day lock serializes quotas across users and worker processes."""
    day_utc = models.DateField(primary_key=True)
    submitted = models.PositiveIntegerField(default=0)


class AIChatJob(models.Model):
    """V7-03.1a: dauerhafter Antwort-Job (PostgreSQL-Queue, ADR-0010).

    Ein Job erzeugt genau eine Assistant-Antwort in einer Unterhaltung. Die Queue
    ist PostgreSQL selbst (``SELECT … FOR UPDATE SKIP LOCKED``); Redis ist nie die
    Quelle der Wahrheit. ``status`` ist der Lebenszyklus des Jobs, ``ledger_state``
    der davon unabhängige finanzielle Zustand der Reservierung. Jede Schreib-
    operation eines Workers ist an ``worker_id`` + ``fencing_token`` + gültige
    Lease gebunden; ein veralteter Worker kann nichts mehr ändern.
    Inhalte (Frage/Antwort) liegen nur in ``AIMessage``; Jobs speichern keine Texte.
    """

    QUEUED = "queued"
    CLAIMED = "claimed"
    RUNNING = "running"
    CANCEL_REQUESTED = "cancel_requested"
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    CANCELLED = "cancelled"
    FAILED = "failed"
    UNCERTAIN = "uncertain"
    STATES = [(s, s) for s in (QUEUED, CLAIMED, RUNNING, CANCEL_REQUESTED, COMPLETED,
                               INCOMPLETE, CANCELLED, FAILED, UNCERTAIN)]
    ACTIVE = (QUEUED, CLAIMED, RUNNING, CANCEL_REQUESTED)
    TERMINAL = (COMPLETED, INCOMPLETE, CANCELLED, FAILED, UNCERTAIN)

    LEDGER_NONE = "none"
    LEDGER_RESERVING = "reserving"        # Korrelations-ID vermerkt, Reservierung angefragt
    LEDGER_RESERVED = "reserved"
    LEDGER_FINALIZED = "finalized"
    LEDGER_UNCERTAIN = "uncertain"
    LEDGER_RELEASED = "released"
    LEDGER_UNACKNOWLEDGED = "unacknowledged"
    LEDGER_STATES = [(s, s) for s in (LEDGER_NONE, LEDGER_RESERVING, LEDGER_RESERVED, LEDGER_FINALIZED,
                                      LEDGER_UNCERTAIN, LEDGER_RELEASED, LEDGER_UNACKNOWLEDGED)]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name="ai_chat_jobs")
    # Audit bleibt beim Löschen der Unterhaltung erhalten (Finanzbelege im Ledger).
    conversation = models.ForeignKey(AIConversation, on_delete=models.SET_NULL, null=True,
                                     related_name="chat_jobs")
    user_message = models.ForeignKey(AIMessage, on_delete=models.SET_NULL, null=True,
                                     related_name="+")
    assistant_message = models.OneToOneField(AIMessage, on_delete=models.SET_NULL, null=True,
                                             related_name="chat_job")
    # Idempotenz je Eigentümer (kein globaler Namensraum -> keine Existenz-Auskunft
    # über fremde Jobs).
    request_id = models.UUIDField()
    fingerprint = models.CharField(max_length=64)
    language = models.CharField(max_length=2, default="fa")
    status = models.CharField(max_length=20, choices=STATES, default=QUEUED)
    worker_id = models.CharField(max_length=64, blank=True, default="")
    fencing_token = models.PositiveBigIntegerField(default=0)
    lease_until = models.DateTimeField(null=True, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    provider_request_sent = models.BooleanField(default=False)
    reservation_id = models.UUIDField(null=True, blank=True)
    ledger_state = models.CharField(max_length=16, choices=LEDGER_STATES, default=LEDGER_NONE)
    checkpoint_sequence = models.PositiveIntegerField(default=0)
    checkpoint_chars = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=40, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"], name="ai_chatjob_queue_idx"),
            models.Index(fields=["owner", "status"], name="ai_chatjob_owner_idx"),
            models.Index(fields=["status", "lease_until"], name="ai_chatjob_lease_idx"),
            models.Index(fields=["reservation_id"], name="ai_chatjob_reservation_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["owner", "request_id"], name="ai_chatjob_owner_request_unique"),
            models.CheckConstraint(
                condition=Q(status__in=["queued", "claimed", "running", "cancel_requested", "completed",
                                        "incomplete", "cancelled", "failed", "uncertain"]),
                name="ai_chatjob_status_valid"),
            models.CheckConstraint(
                condition=Q(ledger_state__in=["none", "reserving", "reserved", "finalized", "uncertain",
                                              "released", "unacknowledged"]),
                name="ai_chatjob_ledger_state_valid"),
            # Laufende Jobs haben immer einen Worker und eine Lease.
            models.CheckConstraint(
                condition=(~Q(status__in=["claimed", "running"])
                           | (Q(lease_until__isnull=False) & ~Q(worker_id=""))),
                name="ai_chatjob_running_has_lease"),
        ]
