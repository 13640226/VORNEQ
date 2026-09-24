from django.db import migrations, models
import django.db.models.deletion


def _identity_for_user(UserIdentity, user_id):
    identity_id = (
        UserIdentity.objects.filter(user_id=user_id)
        .values_list("identity_id", flat=True)
        .first()
    )
    if identity_id is None:
        raise RuntimeError(
            f"Documents identity migration cannot resolve user {user_id} to a canonical Identity."
        )
    return identity_id


def backfill_identity_subjects(apps, schema_editor):
    Document = apps.get_model("documents", "Document")
    DocumentAccess = apps.get_model("documents", "DocumentAccess")
    UserIdentity = apps.get_model("core", "UserIdentity")

    owner_identity_by_document = {}
    for document in Document.objects.all().iterator():
        identity_id = _identity_for_user(UserIdentity, document.created_by_id)
        document.owner_identity_id = identity_id
        document.save(update_fields=["owner_identity"])
        owner_identity_by_document[document.pk] = identity_id

    for access in DocumentAccess.objects.select_related("document").all().iterator():
        identity_id = _identity_for_user(UserIdentity, access.user_id)
        owner_identity_id = owner_identity_by_document[access.document_id]

        if access.role == "owner":
            if access.user_id != access.document.created_by_id or identity_id != owner_identity_id:
                raise RuntimeError(
                    f"Documents identity migration found an inconsistent owner access row {access.pk}."
                )
            access.delete()
            continue

        if identity_id == owner_identity_id:
            raise RuntimeError(
                f"Documents identity migration found owner Identity as collaborator on access row {access.pk}."
            )

        access.identity_id = identity_id
        access.save(update_fields=["identity"])


def reverse_identity_subjects(apps, schema_editor):
    Document = apps.get_model("documents", "Document")
    DocumentAccess = apps.get_model("documents", "DocumentAccess")
    UserIdentity = apps.get_model("core", "UserIdentity")

    user_by_identity = dict(
        UserIdentity.objects.exclude(user_id=None).values_list("identity_id", "user_id")
    )

    for access in DocumentAccess.objects.all().iterator():
        user_id = user_by_identity.get(access.identity_id)
        if user_id is None:
            raise RuntimeError(
                f"Cannot reverse Documents identity migration for Identity {access.identity_id}."
            )
        access.user_id = user_id
        access.save(update_fields=["user"])

    for document in Document.objects.all().iterator():
        owner_user_id = user_by_identity.get(document.owner_identity_id)
        if owner_user_id is None or owner_user_id != document.created_by_id:
            raise RuntimeError(
                f"Cannot reverse Documents identity migration for document {document.pk}."
            )
        DocumentAccess.objects.create(
            document_id=document.pk,
            user_id=document.created_by_id,
            role="owner",
            granted_by_id=document.created_by_id,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0008_contextual_reputation_identity_actor_role"),
        ("documents", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="owner_identity",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="documents_owned",
                to="core.identity",
            ),
        ),
        migrations.AddField(
            model_name="documentaccess",
            name="identity",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="document_access_entries",
                to="core.identity",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="documentaccess",
            name="docs_access_document_user_unique",
        ),
        migrations.RemoveConstraint(
            model_name="documentaccess",
            name="docs_access_single_owner",
        ),
        migrations.RemoveIndex(
            model_name="documentaccess",
            name="docs_access_user_role_idx",
        ),
        migrations.RunPython(backfill_identity_subjects, reverse_identity_subjects),
        migrations.RemoveField(
            model_name="documentaccess",
            name="user",
        ),
        migrations.AlterField(
            model_name="document",
            name="owner_identity",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="documents_owned",
                to="core.identity",
            ),
        ),
        migrations.AlterField(
            model_name="documentaccess",
            name="identity",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="document_access_entries",
                to="core.identity",
            ),
        ),
        migrations.AlterField(
            model_name="documentaccess",
            name="role",
            field=models.CharField(
                choices=[("editor", "Editor"), ("viewer", "Viewer")],
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="documentaccess",
            constraint=models.UniqueConstraint(
                fields=("document", "identity"),
                name="docs_access_document_identity_unique",
            ),
        ),
        migrations.AddIndex(
            model_name="documentaccess",
            index=models.Index(
                fields=["identity", "role"],
                name="docs_access_identity_role_idx",
            ),
        ),
    ]
