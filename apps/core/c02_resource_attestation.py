"""C02 cross-source metadata reconciliation; never grants migration permission.

Control-plane documents MUST be obtained from authenticated Render read-only API
separately from the production Django runtime observation. Caller-supplied JSON
is not itself cryptographic evidence of origin, and NAT/proxy routing means
matching metadata does not prove actual PostgreSQL backend resource identity.
"""
import re

from django.core.management.base import CommandError
from apps.core import c02_operational_binding as binding

EXPECTED_POSTGRES_ID = "dpg-dagru1h42hec73eqr960-a"
EXPECTED_SERVICE_ID = "srv-dadn07eq1p3s73eccau0"
EXPECTED_DATABASE_NAME = "vorneq_production_db"
EXPECTED_DATABASE_USER = binding.EXPECTED_DATABASE_USER
EXPECTED_EXECUTION_ROLE = binding.EXPECTED_EXECUTION_ROLE
EXPECTED_POSTGRES_MAJOR = 18

_SHA40 = re.compile(r"^[0-9a-f]{40}$")


def _require(value, expected, label):
    if value != expected:
        raise CommandError("C02 cross-source mismatch: " + label)


def reconcile_render_metadata(postgres, service, runtime, expected_sha):
    """Verify independently sourced metadata against a read-only session report.

    This is a partial cross-source check, *not* a resource identity proof:
    - no server TLS peer certificate / authenticated backend resource binding
    - runtime JSON could be tampered with between capture and reconciliation
    - no transaction or migration application is authorized
    """
    if not all(isinstance(x, dict) for x in (postgres, service, runtime)):
        raise CommandError("Invalid C02 evidence structure")
    if not isinstance(expected_sha, str) or not _SHA40.fullmatch(expected_sha):
        raise CommandError("Expected SHA must be 40 lowercase hex characters")
    _require(postgres.get("id"), EXPECTED_POSTGRES_ID, "postgres resource")
    _require(postgres.get("databaseName"), EXPECTED_DATABASE_NAME, "Render database")
    _require(postgres.get("databaseUser"), EXPECTED_DATABASE_USER, "Render user")
    _require(postgres.get("status"), "available", "Render PostgreSQL availability")
    _require(postgres.get("role"), "primary", "Render PostgreSQL role")
    _require(str(postgres.get("version")), str(EXPECTED_POSTGRES_MAJOR), "Render PostgreSQL major")
    _require(service.get("id"), EXPECTED_SERVICE_ID, "Render web service")
    _require(service.get("branch"), "main", "Render service branch")
    _require(service.get("autoDeploy"), "no", "Render auto deploy policy")
    _require(service.get("autoDeployTrigger"), "off", "Render deploy trigger")
    _require(service.get("environmentId"), postgres.get("environmentId"), "Render environment")
    _require(
        service.get("serviceDetails", {}).get("region"),
        postgres.get("region"),
        "Render deployment region",
    )
    _require(runtime.get("service_id"), EXPECTED_SERVICE_ID, "runtime service")
    _require(runtime.get("database"), EXPECTED_DATABASE_NAME, "runtime database")
    _require(runtime.get("username"), EXPECTED_EXECUTION_ROLE, "runtime current_user legacy field")
    _require(runtime.get("current_role"), EXPECTED_EXECUTION_ROLE, "runtime current_user")
    _require(runtime.get("session_user"), EXPECTED_DATABASE_USER, "runtime authenticated session_user")
    host = runtime.get("configured_host")
    if not isinstance(host, str) or host.split(".")[0].lower() != EXPECTED_POSTGRES_ID:
        raise CommandError("Configured runtime PostgreSQL host differs from Render resource prefix")
    _require(runtime.get("server_port"), 5432, "runtime PostgreSQL port")
    _require(runtime.get("postgres_major"), EXPECTED_POSTGRES_MAJOR, "runtime PostgreSQL major")
    _require(runtime.get("is_replica"), False, "runtime PostgreSQL primary")
    _require(runtime.get("transaction_read_only"), "on", "runtime read-only transaction")
    _require(runtime.get("deploy_sha"), expected_sha, "runtime deploy SHA")
    # A successful check deliberately cannot be treated as write authorization.
    return {
        "CONTROL_PLANE_METADATA_MATCH": True,
        "DJANGO_RENDER_RUNTIME_METADATA_MATCH": True,
        "POSTGRES_BACKEND_RESOURCE_IDENTITY_PROVEN": False,
        "C02_MIGRATION_GO": False,
    }
