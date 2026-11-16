"""Offline C02 Render control-plane cross-source reconciliation tests."""
from copy import deepcopy
from unittest import TestCase

from django.core.management.base import CommandError
from apps.core.c02_resource_attestation import reconcile_render_metadata

SHA = "a" * 40

DB = {
    "id": "dpg-dagru1h42hec73eqr960-a",
    "databaseName": "vorneq_production_db",
    "databaseUser": "vorneq_prod_app_rot_20261116",
    "environmentId": "evm-da71gna6iojc7385it9g",
    "region": "oregon",
    "role": "primary",
    "status": "available",
    "version": "18",
}
SERVICE = {
    "id": "srv-dadn07eq1p3s73eccau0",
    "branch": "main",
    "environmentId": DB["environmentId"],
    "autoDeploy": "no",
    "autoDeployTrigger": "off",
    "serviceDetails": {"region": "oregon"},
}
RUNTIME = {
    "service_id": SERVICE["id"],
    "deploy_sha": SHA,
    "database": DB["databaseName"],
    "username": "vorneq_production_db_user",
    "current_role": "vorneq_production_db_user",
    "session_user": DB["databaseUser"],
    "configured_host": DB["id"] + ".oregon-postgres.render.com",
    "server_port": 5432,
    "postgres_major": 18,
    "is_replica": False,
    "transaction_read_only": "on",
    "backend_pid": 135,
}


class CrossSourceRenderEvidenceTests(TestCase):
    def verify(self, db=None, service=None, runtime=None, sha=SHA):
        return reconcile_render_metadata(
            deepcopy(DB if db is None else db),
            deepcopy(SERVICE if service is None else service),
            deepcopy(RUNTIME if runtime is None else runtime), sha,
        )

    def test_verified_metadata_does_not_authorize_migration(self):
        result = self.verify()
        self.assertTrue(result["CONTROL_PLANE_METADATA_MATCH"])
        self.assertFalse(result["POSTGRES_BACKEND_RESOURCE_IDENTITY_PROVEN"])
        self.assertFalse(result["C02_MIGRATION_GO"])

    def test_wrong_render_resource_id(self):
        db = deepcopy(DB)
        db["id"] = "dpg-unrelated"
        with self.assertRaises(CommandError):
            self.verify(db=db)

    def test_wrong_render_database_user(self):
        db = deepcopy(DB)
        db["databaseUser"] = "wrong"
        with self.assertRaises(CommandError):
            self.verify(db=db)

    def test_missing_render_version(self):
        db = deepcopy(DB)
        db.pop("version")
        with self.assertRaises(CommandError):
            self.verify(db=db)

    def test_render_role_replica_rejected(self):
        db = deepcopy(DB)
        db["role"] = "replica"
        with self.assertRaises(CommandError):
            self.verify(db=db)

    def test_unavailable_database_rejected(self):
        db = deepcopy(DB)
        db["status"] = "suspended"
        with self.assertRaises(CommandError):
            self.verify(db=db)

    def test_different_environment_rejected(self):
        service = deepcopy(SERVICE)
        service["environmentId"] = "evm-other"
        with self.assertRaises(CommandError):
            self.verify(service=service)

    def test_region_drift_rejected(self):
        service = deepcopy(SERVICE)
        service["serviceDetails"]["region"] = "frankfurt"
        with self.assertRaises(CommandError):
            self.verify(service=service)

    def test_wrong_service_id_rejected(self):
        service = deepcopy(SERVICE)
        service["id"] = "srv-other"
        with self.assertRaises(CommandError):
            self.verify(service=service)

    def test_wrong_runtime_host_resource_rejected(self):
        runtime = deepcopy(RUNTIME)
        runtime["configured_host"] = "dpg-other.oregon-postgres.render.com"
        with self.assertRaises(CommandError):
            self.verify(runtime=runtime)

    def test_wrong_runtime_user_rejected(self):
        runtime = deepcopy(RUNTIME)
        runtime["username"] = "other_user"
        with self.assertRaises(CommandError):
            self.verify(runtime=runtime)

    def test_retired_authenticated_login_rejected(self):
        runtime = deepcopy(RUNTIME)
        runtime["session_user"] = "vorneq_production_db_user"
        with self.assertRaises(CommandError):
            self.verify(runtime=runtime)

    def test_execution_role_drift_rejected(self):
        runtime = deepcopy(RUNTIME)
        runtime["current_role"] = "vorneq_prod_app_rot_20261116"
        with self.assertRaises(CommandError):
            self.verify(runtime=runtime)

    def test_missing_authenticated_login_rejected(self):
        runtime = deepcopy(RUNTIME)
        runtime.pop("session_user")
        with self.assertRaises(CommandError):
            self.verify(runtime=runtime)

    def test_wrong_sha_rejected(self):
        runtime = deepcopy(RUNTIME)
        runtime["deploy_sha"] = "b" * 40
        with self.assertRaises(CommandError):
            self.verify(runtime=runtime)

    def test_short_sha_rejected(self):
        with self.assertRaises(CommandError):
            self.verify(sha="abc")

    def test_writable_transaction_rejected(self):
        runtime = deepcopy(RUNTIME)
        runtime["transaction_read_only"] = "off"
        with self.assertRaises(CommandError):
            self.verify(runtime=runtime)

    def test_wrong_major_version_rejected(self):
        runtime = deepcopy(RUNTIME)
        runtime["postgres_major"] = 17
        with self.assertRaises(CommandError):
            self.verify(runtime=runtime)

    def test_replica_runtime_rejected(self):
        runtime = deepcopy(RUNTIME)
        runtime["is_replica"] = True
        with self.assertRaises(CommandError):
            self.verify(runtime=runtime)

    def test_runtime_metadata_not_a_verified_source(self):
        with self.assertRaises(CommandError):
            self.verify(runtime={"database": DB["databaseName"]})

    def test_auto_deploy_must_be_off(self):
        service = deepcopy(SERVICE)
        service["autoDeploy"] = "yes"
        with self.assertRaises(CommandError):
            self.verify(service=service)
