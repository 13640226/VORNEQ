# SC_07 – Offenlegung: Unabhängigkeit des Reviewers (ENTWURF V1.6)

**Kennung:** SC_07_REVIEWER_INDEPENDENCE_DISCLOSURE_DRAFT_V1.6

**Dokumentstatus:** V1.5 = CORRECTION_REQUIRED · V1.6 = DRAFT / OWNER_ACCEPTANCE_PENDING

**Autorisierung:** DOCUMENTARY_ONLY

**Bezug:** Issue #340 · Audit-Basis ddc5d8853deec7a204c4b8b801faffb2916f41a2

## 0. Ausdrücklich nicht autorisiert

Veröffentlichung dieses Textes als Kommentar in #340 oder an anderer Stelle im Repository

Änderungen an Branch Protection, Rulesets, CODEOWNERS, Rollen oder Berechtigungen

Merge, Deploy oder jede andere operative Maßnahme

Jede dieser Handlungen erfordert eine gesonderte, explizite Owner-Entscheidung.

## 1. Sachverhalt

Repository-Owner ist das Konto 13640226.

Reviews und Freigaben wurden bisher unter anderem über das Konto hamidrezaasadian7-boop abgegeben.

Die bisher dokumentierten Angaben zur tatsächlichen Kontrolle des Reviewer-Kontos hamidrezaasadian7-boop sind nicht vollständig konsistent. Eine unabhängige Verifikation der Kontoinhaberschaft, Zugangskontrolle und organisatorischen Unabhängigkeit liegt derzeit nicht vor.

Owner und Reviewer arbeiten am selben Laptop. Eine technische Trennung von Gerät, Browser-Sitzung, Credentials und 2FA ist nicht nachgewiesen.

## 2. Bewertung

Gemeinsame Kontrolle über beide Konten kann nicht ausgeschlossen werden. Die Unabhängigkeit des Reviewers ist nicht erwiesen. Ein separates GitHub-Konto oder eine organisatorische Zuordnung allein begründet keine Unabhängigkeit.

## 3. Konsequenzen

Reviews und Approvals über das Konto hamidrezaasadian7-boop werden nicht als unabhängige Sicherheitsfreigabe anerkannt, solange die Unabhängigkeit dieses Kontos nicht gesondert nachgewiesen ist; dies gilt für bereits abgegebene wie für künftige Reviews. Die Schließung von SC_07 durch einen anderen Reviewer ändert daran nichts.

Bereits abgegebene Reviews und Approvals bleiben als historische GitHub-Ereignisse bestehen. Eine automatische technische Aufhebung oder Löschung ist damit nicht verbunden.

Diese Reviews und Approvals begründen weder MERGE_GO noch DEPLOY_GO noch die Schließung eines Befunds.

Kein Akzeptanzkriterium aus V3.1-A, V3.1-B, V3.1-C oder OD-10 gilt allein aufgrund eines solchen Reviews als unabhängig verifiziert.

## 4. Anforderungen an einen unabhängigen Reviewer (Vorschlag)

Eine natürliche Person ohne Zugriff auf Owner-Credentials, Owner-Geräte oder gemeinsame Sitzungen

Ein eigenes Gerät, eigene Credentials und eigene 2FA, mit schriftlicher Bestätigung der Trennung

Kein wirtschaftliches oder weisungsgebundenes Abhängigkeitsverhältnis zum Owner in Bezug auf das Prüfergebnis, oder dessen Offenlegung samt Bewertung

Eine dokumentierte Interessenkonflikt-Erklärung vor Prüfbeginn

Least-Privilege-Berechtigungen, deren Umfang und Dauer gesondert freizugeben sind

Benennung durch eine gesonderte, explizite Owner-Entscheidung

Der Reviewer muss Prüfentscheidungen ohne unzulässige Einflussnahme treffen können. Prüfmethoden und Nachweise müssen nachvollziehbar und soweit möglich reproduzierbar sein. Eine Mitwirkung an der Erstellung oder Freigabe der zu prüfenden Nachweise ist offenzulegen und auf Interessenkonflikte zu bewerten. Nachweise, an deren Erstellung oder Freigabe der Reviewer mitgewirkt hat, kann er nicht selbst unabhängig verifizieren.

## 5. Schließungskriterien für SC_07

Gegenstand von SC_07 sind ausschließlich die nachgewiesene Unabhängigkeit des Reviewers und der Abschluss seines Prüfmandats. SC_07 darf erst geschlossen werden, wenn alle folgenden Punkte erfüllt sind:

1. Ein Reviewer nach Abschnitt 4 ist benannt, und die Trennung ist nachgewiesen.
2. Ein Prüfmandat mit definiertem Umfang ist schriftlich festgelegt.
3. Dieser Reviewer hat die Prüfung tatsächlich durchgeführt.
4. Das Prüfergebnis ist dokumentiert und ausgewertet, einschließlich Befunden und deren Behandlung.
5. Die Owner-Entscheidung zur Schließung ist gesondert in #340 festgehalten.

Weder die Benennung allein noch diese Offenlegung schließt SC_07.

## 6. Abgrenzung zu C02

C02 hat zwei eigenständige Voraussetzungen:

(a) eine unabhängige Prüfung im Sinne von SC_07 und

(b) ausreichende Evidenz zur tatsächlichen Identität der Runtime-PostgreSQL-Instanz, gemäß gesondertem C02-Prüfumfang (derzeit ENTWURF, nicht angenommen).

Die Schließung von SC_07 erfüllt höchstens Voraussetzung (a). Sie schließt C02 nicht.

C02 kann auch nach Schließung von SC_07 OPEN_CRITICAL bleiben. Das gilt insbesondere bei den Ergebnissen INCONCLUSIVE oder INCONSISTENT zur Datenbankidentität.

## 7. Status

| Kontrolle | Status |
|---|---|
| SC_07 | OPEN_CRITICAL |
| C02 | OPEN_CRITICAL |
| STOP_340 | ACTIVE |
| Gesamt | SAFE_HOLD / NO_GO |

---

**AUTHORIZATION_SCOPE = DOCUMENTARY_ONLY**

**DOCUMENT_STATUS = DRAFT / OWNER_ACCEPTANCE_PENDING**

**SC_07 = OPEN_CRITICAL**

**C02 = OPEN_CRITICAL**

**STOP_340 = ACTIVE**

**FINAL_STATE = SAFE_HOLD / NO_GO**

Dieses Dokument stellt weder eine operative Freigabe noch eine unabhängige Sicherheitsverifikation dar.

Eine Veröffentlichung in GitHub Issue #340, eine Änderung des Repositorys, der Branch Protection, der Berechtigungen oder irgendeine operative Maßnahme ist nicht autorisiert.
