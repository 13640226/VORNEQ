"""V7-03.1a: Worker für dauerhafte Antwort-Jobs (ADR-0010).

PostgreSQL ist die Queue; Redis ist höchstens ein Weckhinweis. Standard: genau ein
Job, keine Dauerschleife. Ohne ``VORNEQ_AI_CHAT_JOBS_ENABLED`` (bzw.
``…_PRODUCTION_ENABLED``) verweigert der Befehl den Start. Ein übernommener Job wird
nie automatisch erneut gestartet; unklare Fälle bleiben für die Reconciliation.
"""
import socket
import time
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from apps.ai_core import chat_jobs


class Command(BaseCommand):
    help = "Process durable chat jobs (default: one job)."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--max-jobs", type=int, default=1)
        parser.add_argument("--poll-seconds", type=float, default=2.0)

    def handle(self, *args, **options):
        if not chat_jobs.enabled():
            raise CommandError("chat job gate is closed")
        delay, limit = options["poll_seconds"], options["max_jobs"]
        if not 0.5 <= delay <= 60.0 or not 1 <= limit <= 100_000:
            raise CommandError("invalid worker options")
        worker_id = f"{socket.gethostname()[:40]}:{uuid.uuid4().hex[:12]}"
        processed = 0
        while processed < limit:
            try:
                lease = chat_jobs.claim(worker_id)
            except DatabaseError as exc:
                self.stderr.write(f"CHAT_JOB_CLAIM_FAILED kind={type(exc).__name__}")
                raise CommandError("chat job queue unavailable") from exc
            if lease is None:
                if not options["loop"]:
                    break
                time.sleep(delay)
                continue
            status = chat_jobs.run_claimed(lease)
            processed += 1
            self.stdout.write(f"CHAT_JOB_PROCESSED id={lease.job_id} status={status or 'lease_lost'}")
        self.stdout.write(f"CHAT_JOBS_DONE processed={processed}")
