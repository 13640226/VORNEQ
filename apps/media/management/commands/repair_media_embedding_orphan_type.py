from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


TYPE_NAME = "media_mediaembedding"
MIGRATION_NAME = "0002_mediaembedding"


class Command(BaseCommand):
    help = (
        "Repair the known orphan PostgreSQL composite type blocking "
        "media.0002_mediaembedding. The command is fail-closed and only mutates "
        "the database when the expected orphan state is proven."
    )

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("Repair is PostgreSQL-only; refusing to run.")

        migration_recorded = MigrationRecorder(connection).migration_qs.filter(
            app="media",
            name=MIGRATION_NAME,
        ).exists()
        if migration_recorded:
            raise CommandError(
                f"media.{MIGRATION_NAME} is already recorded; refusing repair."
            )

        if TYPE_NAME in connection.introspection.table_names():
            raise CommandError(
                f"Table {TYPE_NAME} exists; refusing to drop a type with a live table."
            )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT t.oid, t.typtype, t.typrelid, n.nspname
                FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE t.typname = %s
                """,
                [TYPE_NAME],
            )
            rows = cursor.fetchall()

            if len(rows) != 1:
                raise CommandError(
                    f"Expected exactly one {TYPE_NAME} type, found {len(rows)}; refusing repair."
                )

            type_oid, type_kind, type_relid, schema_name = rows[0]
            if type_kind != "c" or type_relid != 0 or schema_name != "public":
                raise CommandError(
                    "Type does not match the expected orphan composite state "
                    f"(oid={type_oid}, typtype={type_kind!r}, typrelid={type_relid}, "
                    f"schema={schema_name!r}); refusing repair."
                )

            self.stdout.write(
                self.style.WARNING(
                    f"Confirmed orphan composite type public.{TYPE_NAME} (oid={type_oid})."
                )
            )

            # Deliberately no CASCADE. PostgreSQL will refuse the operation if a
            # real dependency exists, which is safer than removing related objects.
            cursor.execute(f'DROP TYPE "public"."{TYPE_NAME}"')

        self.stdout.write(
            self.style.SUCCESS(
                f"Dropped orphan type public.{TYPE_NAME} without CASCADE. "
                "The normal Django migration may now create MediaEmbedding."
            )
        )
