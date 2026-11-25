"""V4-01 Testhilfe: simuliertes gemeinsames Ledger für gehostete Testläufe.

Seit V4-01 ist auf Staging und Production jeder kostenpflichtige Textaufruf
ledger-gebunden. Tests, die Recovery-, Konversations- oder Quota-Verhalten auf
gehosteten Laufzeiten prüfen, aktivieren daher ein Fake-Ledger statt des früher
erlaubten ledgerlosen Staging-Pfads. Es werden keine echten Reservierungen,
keine Datenbank des Ledgers und keine Netzwerkaufrufe verwendet.
"""
import uuid
from unittest import mock

from apps.ai_ledger.service import Reservation


def fake_reservation():
    return Reservation(id=uuid.uuid4(), amount_micro=1_000, input_price=1, output_price=1)


def start_fake_ledger(testcase):
    """Ledger an, ``reserve``/``settle`` gemockt. Gibt (reserve, settle) zurück."""
    patches = [
        mock.patch("apps.ai_core.views_global.ledger_enabled", return_value=True),
        mock.patch("apps.ai_core.views_phase_b.ledger_enabled", return_value=True),
        mock.patch("apps.ai_core.budgeted_provider.ledger.reserve",
                   side_effect=lambda **_kwargs: fake_reservation()),
        mock.patch("apps.ai_core.budgeted_provider.ledger.settle", return_value="finalized"),
    ]
    started = [p.start() for p in patches]
    for p in patches:
        testcase.addCleanup(p.stop)
    return started[2], started[3]
