# C02 final evidence snapshot — 2026-11-16 (read-only; no release)

**Scope:** Document the observed C02 evidence tied to the verified live Production source, and preserve the NO-GO decision. This is a historical snapshot, **not** a future execution authorization.

| Field | Verified observation / limit |
|---|---|
| Repository | `13640226/VORNEQ` |
| Audited main SHA and Render live deploy SHA | `37b2ce05ae59f984fd9181aa25395d098d24879f` |
| Render live deploy | `dep-dbt33q6k1f9s73an6dmg` (live on 2026-11-15, 22:28 UTC) |
| Render service | `srv-dadn07eq1p3s73eccau0` (Production, Oregon) |
| Render PostgreSQL resource | `dpg-dagru1h42hec73eqr960-a`, PostgreSQL 18, available |
| Django default database / role | `vorneq_production_db` / `vorneq_production_db_user` |
| Runtime / Dashboard Internal URL comparison | Operator's fresh nonce-based HMAC comparison reported **MATCH** on 2026-11-16; credentials and full URL intentionally omitted |
| Runtime SQL read-only observation | `transaction_read_only=on`; `ai_core` migration rows **0**; `public.ai_core%` tables **0** |
| Django production plan | Exactly `0001_initial` and `0002_aichatrequestguard` unapplied, per owner Render Shell screenshots |
| Generated production SQL | `sqlmigrate` generated two CREATE TABLE statements, one explicit CREATE INDEX and declared constraints; **not executed** |
| Locally restored backup | `2026-11-15T14_22Z.dir (1).tar.gz`, 147852 bytes; SHA-256 `30A15C9E679C6523FD3910D0CF73BA7FADBC6934B2A319F938D190FB9C5F96F8` |
| Local PostgreSQL 18.7 | `pg_restore -l`: 828 TOC entries; `pg_restore --single-transaction --exit-on-error`: exit 0; 89 public tables, approximately 18 MB, `django_migrations` present, no `ai_core` migration rows or tables |
| Production mutation | None performed during evidence review |

## Evidence provenance and limits

- Render resource, service and deploy metadata were retrieved independently using read-only Render tools. The live source SHA matched GitHub `main` **at observation time**, not perpetually.
- HMAC matching shows the runtime `DATABASE_URL` equals the Internal Database URL copied from the authenticated Render Dashboard. It is **not** cryptographic PostgreSQL backend attestation; the Render control plane remains a trust assumption.
- The local restore proves a **bounded, successful logical restoration**, not full row-level data integrity, exact current Production state, current PITR recoverability, or backup freshness at a later write.
- The previously documented 2026-11-15 `T11_19Z` archive and its SHA-256 are different evidence; **do not conflate** them with the `T14_22Z` archive verified here.
- The 35 focused PostgreSQL-18 tests cited in PR #629 were performed in disposable lab environments. They do **not** constitute a live Production migration rehearsal.
- Stage C's source currently has `PRODUCTION_WRITE_ENABLED = False`, pinned by a test. No authorized production execution path exists in this snapshot.
- GitHub Issue #407 contains an older conditional one-use owner release bound to SHA `6cd03395bacbde762055076f4722555f097d612a`. That release **does not transfer** to `37b2ce05...` or to the eventual commit from this branch.
- Issue #340 documents `STOP_340` as active pending a properly established scoped release/authority transition. Confirming `RS3=P0` did not grant general migration authority.

## Required before a future Production migration decision

1. Resolve the binding `STOP_340` / C02 authority chain and record the exact limited exception, preserving other holds. Independent human review may be waived by the owner where the owner's authority allows, but no technical control is waived.
2. Independently review and test a **separate** production-enablement patch. Do not flip `PRODUCTION_WRITE_ENABLED` as part of this evidence-only commit.
3. On the **new** deployed SHA, refresh current Render resource mapping, Internal URL comparison, backup/recovery reference and identity from the real Django `default` session.
4. Provide a fresh, SHA-bound, single-use owner authorization, separate from the prior `6cd03395...` record.
5. Permit execution only after a same-process, same-session fail-closed guard validates identity, exact two-step plan, empty pre-state, locks, transaction continuity and pre-commit schema checks. Post-commit checks and redacted evidence are required. No blind retries.
6. Keep Staging, ledger, paid AI, Render settings, and unrelated schemas out of scope.

**Decision on this branch:** `C02=OPEN_CRITICAL`, `STOP_340=ACTIVE_PENDING_VALID_RELEASE`, `PRODUCTION_MIGRATION_GO=NO`, `PAID_AI=OFF`. No merge, deploy, environment change, production migration or privilege escalation authorized by this document.

References: [Issue #407](https://github.com/13640226/VORNEQ/issues/407), [Issue #340](https://github.com/13640226/VORNEQ/issues/340), [Stage C PR #629](https://github.com/13640226/VORNEQ/pull/629).
