"""Read-only PostgreSQL session continuity attestation.

A PID match alone is insufficient: verify the exact Django connection object,
the underlying driver connection object, transaction and server identity.
Never authorizes or performs schema changes.
"""
from dataclasses import dataclass

from django.core.management.base import CommandError


@dataclass(frozen=True)
class SessionIdentity:
    connection_id: int
    driver_id: int
    backend_pid: int
    database: str
    username: str
    server_address: str
    server_port: int
    readonly: str
    replica: bool
    login_user: str  # SESSION_USER; distinct from username/current_user.


def capture_session(connection):
    if connection.vendor != "postgresql" or connection.connection is None:
        raise CommandError("Missing live PostgreSQL connection")
    driver = connection.connection
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_backend_pid(), current_database(), current_user, "
            "inet_server_addr()::text, inet_server_port(), "
            "current_setting('transaction_read_only'), pg_is_in_recovery(), session_user"
        )
        row = cursor.fetchone()
    if connection.connection is not driver:
        raise CommandError("Driver connection replaced during observation")
    if row is None or len(row) != 8:
        raise CommandError("Incomplete PostgreSQL session observation")
    pid, db, user, addr, port, readonly, replica, login_user = row
    if not isinstance(pid, int) or not db or not user or not login_user or not addr or not isinstance(port, int):
        raise CommandError("Incomplete PostgreSQL session identity")
    if readonly != "on" or replica is not False:
        raise CommandError("Read-only primary connection required")
    return SessionIdentity(id(connection), id(driver), pid, db, user, addr, port, readonly, replica, login_user)


def assert_same_session(connection, initial):
    if id(connection) != initial.connection_id:
        raise CommandError("Django connection object changed")
    if connection.connection is None or id(connection.connection) != initial.driver_id:
        raise CommandError("PostgreSQL driver connection replaced")
    current = capture_session(connection)
    if current != initial:
        raise CommandError("PostgreSQL session identity changed")
    return current
