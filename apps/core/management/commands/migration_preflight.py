from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.exceptions import InconsistentMigrationHistory
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = (
        "Run read-only migration safety checks before migrate. "
        "Does not mutate schema or migration history."
    )

    def handle(self, *args, **options):
        self.stdout.write("Running migration preflight...")

        try:
            executor = MigrationExecutor(connection)
            loader = executor.loader

            conflicts = loader.detect_conflicts()
            if conflicts:
                rendered = ", ".join(
                    f"{app}: {', '.join(names)}"
                    for app, names in sorted(conflicts.items())
                )
                raise CommandError(
                    f"Conflicting migration leaf nodes detected: {rendered}"
                )

            loader.check_consistent_history(connection)
        except InconsistentMigrationHistory as exc:
            raise CommandError(f"Inconsistent migration history: {exc}") from exc

        targets = loader.graph.leaf_nodes()
        plan = executor.migration_plan(targets)

        if plan:
            self.stdout.write(
                self.style.WARNING(
                    f"Pending migrations: {len(plan)} operation(s) in migration plan."
                )
            )
            for migration, backwards in plan:
                direction = "unapply" if backwards else "apply"
                self.stdout.write(
                    f"  {direction}: {migration.app_label}.{migration.name}"
                )
        else:
            self.stdout.write("No pending migrations.")

        self.stdout.write(
            self.style.SUCCESS(
                "Migration preflight passed: history is consistent and no conflicts were detected."
            )
        )
