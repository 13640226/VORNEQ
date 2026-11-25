import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.environment_parity import build_snapshot, compare_snapshots, dumps


class Command(BaseCommand):
    help = (
        "Read-only Environment-Parity-Audit. Ohne Argumente: bereinigter JSON-Snapshot "
        "dieser Umgebung (keine Secrets, keine Schreibzugriffe, keine externen Aufrufe). "
        "Mit --compare STAGING.json PRODUCTION.json: Vergleich zweier Snapshots, "
        "gruppiert in A (unnötig), B (erlaubt), C (Staging zuerst), D (Architektur), "
        "NV (nicht prüfbar). Exit-Code ungleich 0 bei INVALID oder DRIFT."
    )

    def add_arguments(self, parser):
        parser.add_argument("--compare", nargs=2, metavar=("STAGING_JSON", "PRODUCTION_JSON"))
        parser.add_argument("--no-database", action="store_true",
                            help="Migrationen, Systemdaten und Konten nicht lesen.")
        parser.add_argument("--allow-drift", action="store_true",
                            help="Bei DRIFT mit Exit-Code 0 enden (Bericht bleibt unverändert).")

    def handle(self, *args, **options):
        if options["compare"]:
            snapshots = []
            for raw_path in options["compare"]:
                path = Path(raw_path)
                try:
                    snapshots.append(json.loads(path.read_text(encoding="utf-8")))
                except (OSError, ValueError) as exc:
                    raise CommandError(f"Snapshot nicht lesbar: {path.name} ({type(exc).__name__})") from exc
            result = compare_snapshots(*snapshots)
            self.stdout.write(dumps(result))
            if result["status"] == "INVALID":
                raise CommandError("Vergleich INVALID: " + "; ".join(result["invalid"]))
            if result["status"] == "DRIFT" and not options["allow_drift"]:
                raise CommandError("Umgebungsabweichung (DRIFT) gefunden; siehe Gruppen A/D.")
            return

        report = build_snapshot(include_database=not options["no_database"])
        self.stdout.write(dumps(report))
        if report["status"] != "COMPLETE":
            raise CommandError("Snapshot INVALID: " + ", ".join(report["errors"]))
