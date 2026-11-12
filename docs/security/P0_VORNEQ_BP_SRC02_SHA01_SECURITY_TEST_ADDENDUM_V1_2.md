# VORNEQ — Sicherheitsnachtrag V1.2 zum isolierten Branch-Protection-Testplan

**Dokument-ID:** `P0_VORNEQ_BP_SRC02_SHA01_SECURITY_TEST_ADDENDUM_V1_2`  
**Repository:** `13640226/VORNEQ`  
**Referenz-SHA:** `7cd374b0954eaf97ae89725e327c7f92eb664585`  
**Datum:** 12.11.2026  
**Modus:** `STRICT_READ_ONLY / DOCUMENTARY_ONLY`  
**Status:** `THREAT_MODEL_EXTENDED / EXECUTION_NOT_AUTHORIZED`  
**Verweise:** [PR #580](https://github.com/13640226/VORNEQ/pull/580), [Governance Issue #448](https://github.com/13640226/VORNEQ/issues/448), [Rewire Issue #340](https://github.com/13640226/VORNEQ/issues/340).

## 1. Zweck und Bewertung

Dieser Nachtrag erweitert den bestehenden Testplan um drei Angriffswege, die einen formalen PASS ohne wirksame technische Vertrauensgrenze ermöglichen können:

- **SRC-09 — P0/KRITISCH:** Abfluss des privaten Trusted-Gate-App-Schlüssels.
- **SRC-10 — P0/KRITISCH:** Überschreiben eines negativen Commit-Status durch ein späteres positives Ergebnis im selben Kontext.
- **PERM-08 — HIGH:** Missbrauch eines `push`-Workflows auf einem Feature-Branch ohne existierende Pull Request.

Es handelt sich um dokumentierte Bedrohungsszenarien; ihre konkrete Ausnutzbarkeit für die aktuellen VORNEQ-Berechtigungen ist nicht vollständig runtime-verifiziert. Keine unabhängige Sicherheitsfreigabe wird erteilt.

## 2. SRC-09 — Abfluss des Trusted-Gate-Schlüssels

**Bedrohung:** Same-Repository-PR-Workflows können je nach Kontext Repository-Secrets nutzen. Wird der private Schlüssel einer separaten Gate-App als gewöhnliches Repository-Secret bereitgestellt, kann PR-beeinflusster Workflow-Code die App-Identität missbrauchen. App-ID-Pinning wäre dadurch wirkungslos.

**Sicherheitsanforderungen:**
1. Kein allgemein für PR-/Feature-Branch-Workflows zugängliches Repository-Secret für Gate-App-Schlüssel.
2. Bevorzugt externer, unabhängiger Gate-Service mit gesichert verwahrten Credentials; alternativ restriktives Environment mit begrenzten zulässigen Referenzen und vertrauenswürdigem Job.
3. `main`-Environment-Restriktion allein ist nicht ausreichend, wenn ein privilegierter Default-Branch-Workflow untrusted PR-Inhalte ausführt.
4. Kein Ausführen von PR-Skripten, Executables oder ungeprüften Artefakten im privilegierten Gate-Kontext.
5. Least-Privilege-Zugriff, Rotation und Widerruf der Gate-Credentials dokumentieren.

**Isolierte Negativtests:**
- **SRC-09A:** Feature-Branch-Workflow versucht, synthetisches Gate-Secret zu lesen → verweigert/nicht verfügbar.
- **SRC-09B:** PR-Workflow referenziert geschütztes Environment → kein unautorisierter Secret-Zugriff.
- **SRC-09C:** Untrusted `workflow_run`-Eingaben beeinflussen privilegierten Gate-Nachfolger → keine unautorisierte Signierung/Statusveröffentlichung.
- **SRC-09D:** Manipuliertes PR-Artefakt → ausschließlich als untrusted Data behandelt, nicht ausgeführt.
- **SRC-09E:** Widerrufenes synthetisches Credential nach Rotation → abgelehnt.

**Ausschließlich synthetische Credentials; keine echten App-Schlüssel lesen oder übertragen.**

## 3. SRC-10 — Überschreiben eines Commit-Status

**Bedrohung:** Für denselben Commit-Status-Kontext bestimmt die neueste Statusmeldung den aktuellen kombinierten Zustand. Ein untrusted Publisher mit `statuses: write` könnte ein legitimes `merge-authorization=failure` auf demselben SHA mit einem späteren `success` überlagern.

**Sicherheitsanforderungen:**
- Authentisierte, eindeutig vertrauenswürdige Statusquelle statt bloßer Kontextnamen-/GitHub-Actions-App-ID-Prüfung.
- Untrusted Workflows dürfen keinen gültigen Gate-Status unter der Trusted-App-Identität erzeugen.
- PR-Head-SHA, Autorisierung, Widerruf und Aktualität vor der finalen Entscheidung erneut prüfen; Race Conditions fail-closed behandeln.

**Isolierte Negativtests:**
- **SRC-10A:** Legitimes `failure`, anschließend fremdes `success` auf gleichem SHA/Context → keine Freigabe.
- **SRC-10B:** Zwei Apps senden gleichen Context → nur autorisierte Quelle akzeptiert.
- **SRC-10C:** Spätere vertrauenswürdige Ablehnung nach `success` → Freigabe widerrufen.
- **SRC-10D:** Status auf altem Head SHA → keine Freigabe.
- **SRC-10E:** Asynchrone Statusereignisse in veränderter Reihenfolge → keine Freigabe aus veralteter Entscheidung.

`AC_BP_SRC_10 = UNTRUSTED_STATUS_CANNOT_OVERRIDE_TRUSTED_DENIAL`

## 4. PERM-08 — Push-Workflow auf Feature-Branch

**Bedrohung:** Ein `on: push`-Workflow kann auf einem Feature-Branch aus dessen Workflow-Version laufen, schon bevor eine PR existiert. Wirksame `GITHUB_TOKEN`-Berechtigungen ergeben sich aus Repository- und übergeordneten Richtlinien, Workflow-/Job-Konfiguration und Eventkontext.

**Sicherheitsanforderungen:**
- Standardrechte und tatsächlich wirksame Berechtigungen für Push auf Feature-Branches bestimmen.
- Kein privilegierter Merge-Status durch untrusted Feature-Branch-Workflows.
- Keine direkten oder indirekten Gate-Secrets.
- Vor PR-Erstellung veröffentlichte Statusmeldungen dürfen eine spätere PR-spezifische Owner-Freigabe nicht ersetzen.

**Isolierte Negativtests:**
- **PERM-08A:** Feature-Push mit eingeschränktem Token → kein geschützter Merge-Status.
- **PERM-08B:** Workflow beantragt `statuses: write` → effektive Rechte erfassen und Richtlinie prüfen.
- **PERM-08C:** Push vor PR-Erstellung → keine verwertbare spätere Autorisierung.
- **PERM-08D:** Nachträgliche PR-Erstellung → alte Statusmeldungen ersetzen keine Owner-Freigabe.
- **PERM-08E:** Feature-Branch fordert Trusted-Gate-Environment an → unautorisierter Zugriff verweigert.

## 5. Trusted-Gate-Architektur

- Gate-Code ausschließlich aus einer vertrauenswürdigen Referenz (z. B. sicher konfigurierte `pull_request_target`-/`workflow_run`-Ausführung ohne untrusted Code; bevorzugt unabhängiger GitHub-App-Service).
- Eine separate App ist nur sinnvoll, wenn ihr Schlüssel, ihre ausführbare Logik und ihre Statusentscheidungen von PR-Workflows isoliert sind.
- GitHub Actions App-ID `15368` bezeichnet nicht einen konkreten Workflow und ist allein keine ausreichende Vertrauensgrenze.
- Gate muss nach Abschluss erforderlicher Checks erneut prüfen: PR-Head-SHA, Check-Ergebnisse, Herkunft, erforderliche tatsächliche `success`-Werte, Owner-Autorisierung, Widerruf und Aktualität.
- `workflow_run` ist kein atomarer Abschlussnachweis. Fehlende, laufende, übersprungene, neutrale oder veraltete Checks müssen fail-closed behandelt werden.
- Kein Path-Filter am Trusted Gate, der die Gate-Ausführung stillschweigend unterdrückt.
- Kein priviligiertes Ausführen ungeprüfter PR-Artefakte oder Befehle.

## 6. Ruleset-Verfügbarkeit und Testumgebung

Vor jeder Einrichtung GitHub-Plan, Repo-Typ, verfügbaren Ruleset-Funktionsumfang und effektive Token-Berechtigungen feststellen. Die Regel „Require workflows to pass“ ist nicht pauschal für persönliche Repositories verfügbar. Für isolierte Durchsetzungstests nur autorisiertes Test-Repository mit synthetischen Daten/Secrets verwenden. `enforcement: disabled` beweist keine Sperrwirkung; eine tatsächlich aktive Schutzregel darf ausschließlich im isolierten Testziel geprüft werden.

## 7. Recovery und Administration

**`AC_BP_REC_02 = AUTHORIZED_OWNER_CAN_RECOVER_RULESET_CONFIGURATION`**

Im isolierten Test nachweisen, dass der berechtigte Repository-Administrator auch bei `bypass_actors=[]` die Ruleset-Konfiguration im Recovery-Fall bearbeiten/deaktivieren und danach sicher wiederherstellen kann. Die administrative Regelverwaltung ist von einem Push-/Merge-Bypass zu unterscheiden. Jeder Recovery-Schritt ist zu dokumentieren.

## 8. Zusätzliche Akzeptanzkriterien

```text
AC_BP_SRC_09A=TRUSTED_GATE_SECRET_ISOLATED
AC_BP_SRC_09B=FEATURE_BRANCH_SECRET_ACCESS_DENIED
AC_BP_SRC_09C=PRIVILEGED_WORKFLOW_NOT_INFLUENCED_BY_UNTRUSTED_CODE
AC_BP_SRC_09D=COMPROMISED_CREDENTIAL_ROTATION_TESTED

AC_BP_SRC_10A=UNTRUSTED_STATUS_OVERWRITE_BLOCKED
AC_BP_SRC_10B=STATUS_SOURCE_IDENTITY_VERIFIED
AC_BP_SRC_10C=STALE_STATUS_CANNOT_AUTHORIZE
AC_BP_SRC_10D=STATUS_RACE_HANDLED_FAIL_CLOSED

AC_BP_PERM_08A=FEATURE_PUSH_TOKEN_PERMISSIONS_VERIFIED
AC_BP_PERM_08B=UNAUTHORIZED_STATUS_WRITE_PREVENTED
AC_BP_PERM_08C=PRE_PR_STATUS_CANNOT_AUTHORIZE_MERGE

AC_BP_GATE_01=TRUSTED_CODE_ONLY
AC_BP_GATE_02=REQUIRED_CHECK_COMPLETION_VERIFIED
AC_BP_GATE_03=NO_PATH_FILTER_BYPASS
AC_BP_GATE_04=PR_SHA_REVALIDATED

AC_BP_REC_02=AUTHORIZED_ADMIN_RECOVERY_VERIFIED
```

Dokumentation ersetzt keine ausgeführten und reproduzierbaren Negativtests.

## 9. Status / Entscheidungsgrenzen

```text
DOCUMENT=P0_VORNEQ_BP_SRC02_SHA01_SECURITY_TEST_ADDENDUM_V1_2
REFERENCE_SHA=7cd374b0954eaf97ae89725e327c7f92eb664585
BP_SRC_02=OPEN_CRITICAL
SRC_09=ADDED_CRITICAL
SRC_10=ADDED_CRITICAL
PERM_08=ADDED_HIGH
TRUSTED_GATE_CREDENTIAL_ISOLATION=NOT_VERIFIED
STATUS_OVERWRITE_PROTECTION=NOT_VERIFIED
FEATURE_PUSH_TOKEN_SCOPE=NOT_VERIFIED
TRUSTED_GATE_RACE_HANDLING=NOT_VERIFIED
RULESET_RECOVERY=NOT_TESTED
DOCUMENTARY_STATUS=READY_FOR_REVIEW
NEGATIVE_TESTS=NOT_EXECUTED
TEST_REPOSITORY=NOT_CREATED
RULESET_ACTIVATION=NOT_AUTHORIZED
COMMIT=NO
PUSH=NO
MERGE=NO
WORKFLOW_DISPATCH=NO
DEPLOY=NO
DATABASE_ACCESS=NO
BRANCH_PROTECTION_GO=NO
EXECUTION_AUTHORIZATION=NONE
FINAL_STATE=DOCUMENTARY_TEST_PLAN_READY_FOR_REVIEW
```

**Nächster Schritt:** Dokumentarische Prüfung und gesonderte Owner-Autorisierung für ein isoliertes Test-Repository mit synthetischen Credentials, klarer Testidentität, begrenzten Berechtigungen und vorab festgelegtem Recovery-Verfahren. Keine Änderung am produktiven Repository `13640226/VORNEQ` ist durch diesen Nachtrag genehmigt.

**END OF SECURITY TEST ADDENDUM V1.2**