"""Worker command for a separately provisioned Render Background Worker.

The durable PostgreSQL queue is source of truth; Redis is only an optional
wake signal. Claim once; RUNNING/UNCERTAIN jobs must be reconciled manually.
"""
import time
from django.core.management.base import BaseCommand, CommandError
from apps.ai_core.image_generation.policy import enabled, paid_worker_enabled, worker_enabled
from apps.ai_core.image_generation.service import process_next_image_job


class Command(BaseCommand):
    help = "Process image jobs. Default: one job, no recurring background work."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--poll-seconds", type=float, default=3.0)

    def handle(self, *args, **options):
        if not (enabled() or worker_enabled() or paid_worker_enabled()):
            raise CommandError("image generation gate is closed")
        delay = options["poll_seconds"]
        if not 1.0 <= delay <= 60.0:
            raise CommandError("invalid polling interval")
        while True:
            job_id = process_next_image_job()
            if job_id:
                self.stdout.write("IMAGE_JOB_PROCESSED id={}".format(job_id))
            if not options["loop"]:
                break
            time.sleep(delay)
