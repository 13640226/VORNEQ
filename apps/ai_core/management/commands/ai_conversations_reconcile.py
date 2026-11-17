"""Reconcile stale PENDING conversation turns and report ledger divergence.

A turn stays PENDING when the process was interrupted after the request was
durably recorded, or when PostgreSQL failed after the provider call. This
command never calls a provider and never writes to the ledger database.

* default (report only): counts, no writes
* --apply: for each PENDING assistant turn older than --older-than-minutes
    - if Redis still holds the request's result -> finalize from it
    - otherwise -> mark "uncertain" (error_code "interrupted"); never retried
* ledger report (read-only, separate database): reservations of the affected
  actors in the affected time window that no conversation message references.
  Legacy ask-global reservations are never referenced either, so the number is
  an upper bound for manual review, not proof of a lost conversation turn.

Output contains only counts and IDs, never message content.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError
from django.utils import timezone

from apps.ai_core import request_recovery
from apps.ai_core.conversations import service
from apps.ai_core.models import AIMessage


class Command(BaseCommand):
    help = "Reconcile stale PENDING AI conversation turns (no provider call, no ledger write)"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--older-than-minutes", type=int, default=10)

    def handle(self, *args, **options):
        minutes = options["older_than_minutes"]
        if minutes < 3:
            raise CommandError("--older-than-minutes must be at least 3 (provider timeout + grace)")
        cutoff = timezone.now() - timedelta(minutes=minutes)
        try:
            stale = list(AIMessage.objects.filter(role=AIMessage.ROLE_ASSISTANT, status=AIMessage.STATUS_PENDING,
                                                  created_at__lt=cutoff)
                         .select_related("conversation").order_by("created_at"))
        except DatabaseError as exc:
            raise CommandError("conversation database unavailable") from exc
        from_cache = uncertain = 0
        if options["apply"]:
            for message in stale:
                cached = request_recovery.peek_cached_result(message.request_id) if message.request_id else None
                try:
                    if cached is not None:
                        from_cache += service.finalize_from_cache(message.id, cached)
                    else:
                        uncertain += service.mark_uncertain(message.id)
                except DatabaseError as exc:
                    raise CommandError("conversation database unavailable during apply") from exc
        self.stdout.write(f"AI_CONVERSATIONS_STALE_PENDING count={len(stale)} older_than_minutes={minutes}")
        if options["apply"]:
            self.stdout.write(f"AI_CONVERSATIONS_RECONCILED from_cache={from_cache} marked_uncertain={uncertain}")
        self.stdout.write(f"AI_LEDGER_UNLINKED_RESERVATIONS {self._ledger_report(stale)}")

    def _ledger_report(self, stale):
        if not stale:
            return "count=0"
        try:
            from apps.ai_ledger.models import BudgetReservation

            linked = set(AIMessage.objects.exclude(ledger_reservation_id=None)
                         .values_list("ledger_reservation_id", flat=True))
            total = 0
            for message in stale:
                window = (message.created_at - timedelta(minutes=1), message.created_at + timedelta(minutes=5))
                ids = BudgetReservation.objects.filter(actor_id=message.conversation.owner_id,
                                                       created_at__range=window).values_list("id", flat=True)
                total += sum(1 for reservation_id in ids if reservation_id not in linked)
            return f"count={total} (upper bound; includes legacy ask-global reservations)"
        except Exception:  # noqa: BLE001 - the ledger is a separate, optional database
            return "unavailable"
