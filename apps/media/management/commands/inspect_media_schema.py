from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


class Command(BaseCommand):
    help = "Inspect MediaEmbedding migration/schema state without mutating the database."

    def handle(self, *args, **options):
        target_table = "media_mediaembedding"
        target_migration = "0002_mediaembedding"

        self.stdout.write("=" * 72)
        self.stdout.write("MEDIA SCHEMA INSPECTION (READ-ONLY)")
        self.stdout.write("=" * 72)
        self.stdout.write(f"DATABASE VENDOR: {connection.vendor}")

        migration_qs = MigrationRecorder(connection).migration_qs.filter(app="media")
        recorded = list(migration_qs.order_by("name").values_list("name", flat=True))
        self.stdout.write(f"RECORDED MEDIA MIGRATIONS: {recorded}")
        self.stdout.write(
            f"{target_migration} RECORDED: {target_migration in recorded}"
        )

        table_names = connection.introspection.table_names()
        table_exists = target_table in table_names
        self.stdout.write(f"TABLE EXISTS: {table_exists}")

        if connection.vendor != "postgresql":
            self.stdout.write(
                "PostgreSQL catalog inspection skipped: current database is not PostgreSQL."
            )
            self.stdout.write("INSPECTION COMPLETE — NO CHANGES WERE MADE")
            return

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    t.oid,
                    t.typname,
                    t.typtype,
                    t.typrelid,
                    c.relkind,
                    n.nspname
                FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                LEFT JOIN pg_class c ON c.oid = t.typrelid
                WHERE t.typname = %s
                ORDER BY n.nspname, t.oid
                """,
                [target_table],
            )
            type_rows = cursor.fetchall()
            self.stdout.write(f"PG_TYPE ROWS ({len(type_rows)}):")
            for row in type_rows:
                self.stdout.write(f"  {row}")

            cursor.execute(
                """
                SELECT
                    c.oid,
                    c.relname,
                    c.relkind,
                    n.nspname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = %s
                ORDER BY n.nspname, c.oid
                """,
                [target_table],
            )
            class_rows = cursor.fetchall()
            self.stdout.write(f"PG_CLASS ROWS ({len(class_rows)}):")
            for row in class_rows:
                self.stdout.write(f"  {row}")

            cursor.execute(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                ORDER BY ordinal_position
                """,
                [target_table],
            )
            columns = cursor.fetchall()
            self.stdout.write(f"COLUMNS ({len(columns)}):")
            for row in columns:
                self.stdout.write(f"  {row}")

            if table_exists:
                cursor.execute(f'SELECT COUNT(*) FROM "{target_table}"')
                self.stdout.write(f"ROW COUNT: {cursor.fetchone()[0]}")

                cursor.execute(
                    """
                    SELECT
                        con.conname,
                        con.contype,
                        pg_get_constraintdef(con.oid)
                    FROM pg_constraint con
                    JOIN pg_class rel ON rel.oid = con.conrelid
                    JOIN pg_namespace n ON n.oid = rel.relnamespace
                    WHERE n.nspname = 'public'
                      AND rel.relname = %s
                    ORDER BY con.conname
                    """,
                    [target_table],
                )
                constraints = cursor.fetchall()
                self.stdout.write(f"CONSTRAINTS ({len(constraints)}):")
                for row in constraints:
                    self.stdout.write(f"  {row}")

                cursor.execute(
                    """
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = %s
                    ORDER BY indexname
                    """,
                    [target_table],
                )
                indexes = cursor.fetchall()
                self.stdout.write(f"INDEXES ({len(indexes)}):")
                for row in indexes:
                    self.stdout.write(f"  {row}")

            if type_rows:
                type_oids = [row[0] for row in type_rows]
                cursor.execute(
                    """
                    SELECT
                        dep.classid::regclass::text,
                        dep.objid,
                        dep.refclassid::regclass::text,
                        dep.refobjid,
                        dep.deptype
                    FROM pg_depend dep
                    WHERE dep.refobjid = ANY(%s)
                       OR dep.objid = ANY(%s)
                    ORDER BY dep.refobjid, dep.objid
                    """,
                    [type_oids, type_oids],
                )
                dependencies = cursor.fetchall()
                self.stdout.write(f"TYPE DEPENDENCIES ({len(dependencies)}):")
                for row in dependencies:
                    self.stdout.write(f"  {row}")

        self.stdout.write("=" * 72)
        self.stdout.write("INSPECTION COMPLETE — NO CHANGES WERE MADE")
        self.stdout.write("=" * 72)
