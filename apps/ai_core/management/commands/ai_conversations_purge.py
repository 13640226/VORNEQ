"""Permanently delete AI conversations whose 30-day trash period has ended (D2).

Run daily (e.g. Render cron job). Writes only to ai_core conversation tables of
the configured default database; never touches the ledger or the request guard.
"""
from django.core.management.base import BaseCommand

from apps.ai_core.conversations.service import purge_expired


class Command(BaseCommand):
    help = "Purge AI conversations that have been in the trash longer than the retention period"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        from datetime import timedelta

        from django.conf import settings
        from django.utils import timezone

        from apps.ai_core.models import AIConversation

        from django.core.management.base import CommandError
        from django.db import DatabaseError

        try:
            if options["dry_run"]:
                cutoff = timezone.now() - timedelta(days=settings.VORNEQ_AI_CONVERSATION_TRASH_DAYS)
                count = AIConversation.objects.filter(deleted_at__isnull=False, deleted_at__lt=cutoff).count()
                self.stdout.write(f"AI_CONVERSATIONS_PURGE_DRY_RUN expired={count}")
                return
            deleted = purge_expired()
        except DatabaseError as exc:
            # Nothing partial is reported as done; a rerun is safe (idempotent).
            raise CommandError("conversation database unavailable; nothing purged") from exc
        self.stdout.write(f"AI_CONVERSATIONS_PURGED rows={deleted}")
