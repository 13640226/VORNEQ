# ADR-016 Rollback Runbook — DRAFT v1.5

**Status:** Draft v1.5 — Policy-stable / Docs-ready with explicitly open prerequisites  
**Baseline:** `main@803a6d153a1819c41d678b3b0e6d5f60da4f4b5f`  
**Sources:** ADR-016, `docs/disaster-recovery.md`, `.github/workflows/dr-staging-rehearsal.yml`, `scripts/dr_staging_rehearsal.py`  
**Policy state:** ADR-016 = Proposed (frozen policy؛ implementation deferred)

## Changelog v1.3 → v1.4 (R5 patch)

- F1 — Section جدید «Forward-Fix Path (Default)» با دو mode
- F2 — Section 4.2: تفکیک صریح authority برای 4.1 vs 4.2
- F3 — حل‌شده با Section جدید Forward-Fix (ordering vs stop/freeze)
- F4 — Section 11 reverse migration row: eligible cases only؛ F-* prohibited
- F5 — Section 9.0: approval boundary preservation strategy (DB Operator prep + Change Approver authorize؛ stronger boundaries preserved)
- F6 — Section 11 row #11: (execution gated by #2)
- F7 — Section 15.1: three-layer status برچسب‌گذاری
- F8 — Section 15.1 vs 15.3: تمایز placeholder vs field value

## Changelog v1.4 → v1.5

یک amendment حداقلی در Section 3.5.1 — برچسب صریح ordering deviation از D2 در Mode A. هیچ تغییر دیگری اعمال نشد.

---

## 0. Scope & Audience

Scope: rollback، forward-fix و restore procedures برای migrationهای ADR-016.  
Audience: Change Approver · Incident Lead · Database Operator · Application Verifier  
Not in scope: Auth remediation، DB mapping، ADR-017، ADR-018، PR #239.

---

## 1. Two-Rehearsal Distinction (Locked)

| لایه | چیست | چه چیزی اثبات می‌کند |
|---|---|---|
| Repo-contract rehearsal | CI Backup Restore Rehearsal (ephemeral PG) | migration/backup contract در repo |
| Infrastructure rehearsal | DR Staging Rehearsal (manual، isolated target) | restore واقعی + verification + RTO |

قاعده: repo-contract rehearsal هرگز جای qualifying infrastructure rehearsal را نمی‌گیرد و به‌عنوان آن محسوب نمی‌شود.

تصریح درباره D5: D5 مجموعه‌ای از prerequisites مستقل است (شامل backup freshness، rehearsal freshness، isolated target، verification، evidence capture و ...). Infrastructure rehearsal فقط prerequisite مربوط به «successful restore rehearsal with approved freshness» را satisfy می‌کند. Infrastructure rehearsal به‌تنهایی کل D5 را satisfy نمی‌کند؛ سایر prerequisites D5 همچنان مستقل باقی می‌مانند و باید جداگانه تأمین شوند.

---

## 2. Canonical Ordering (per D2 — Locked، rollback/remediation پس از STOP)

این ترتیب برای rollback/remediation پس از STOP است. Forward-fix در حالت‌های بدون STOP تابع Section جدید «Forward-Fix Path» (بخش ۳.۵) است.

1. Stop traffic
2. Freeze writes
3. Rollback service layer (compatibility guard، بخش ۷.۱)
4. Reverse schema (eligibility، بخش ۷.۲)
5. Data restoration or reconciliation — conditional؛ approval صریح
6. Resume traffic بعد از تأیید compatibility
7. Health / smoke verification

---

## 3. Preconditions

- [ ] Pre-migration state snapshot
- [ ] D5 backup-freshness satisfied (production backup <24h)
- [ ] Infrastructure rehearsal freshness ≤30 days
- [ ] `migrate --plan` مطابق انتظار؛ migration graph verified
- [ ] Change window اعلام‌شده
- [ ] On-call named و present
- [ ] Fill-at-change-time: Data Preflight (بخش ۳.۶) → SAFE
- [ ] Fill-at-change-time: per-change execution budget
- [ ] Fill-at-change-time: R-Data-Cond re-evaluation (شامل `core.0010_identityhandle`)

---

## 3.5 Forward-Fix Path (Default Strategy — NEW per F1/F3)

ADR-016 forward-fix را strategy پیش‌فرض تعریف می‌کند. این section دو mode متفاوت را تفکیک می‌کند تا با D2 rollback ordering اشتباه گرفته نشود.

### 3.5.1 Mode A — Forward-Fix پس از STOP (Containment Active)

اگر پیش از تصمیم به forward-fix یک STOP criterion (بخش ۴) فعال شده باشد:

1. Traffic Stop و Write Freeze حفظ می‌شوند (بخش‌های ۵.۱، ۵.۲) — containment برقرار می‌ماند.
2. Fix تهیه می‌شود — branch جدا، normal repository change-control.
3. Fix review می‌شود — طبق process معمول repo.
4. Deployment authorization صریح صادر می‌شود (بخش ۱۱).
5. Deploy در حالت containment انجام می‌شود — traffic همچنان stopped، writes همچنان frozen.
6. Compatibility validation — schema/code alignment بررسی می‌شود (بخش ۷.۱).
7. Health / smoke verification (بخش ۱۲.۲ + ۱۲.۳).
8. Resume طبق approval موجود — Change Approver + Incident Lead (بخش ۱۱).

Guard: این mode ordering جدید نمی‌سازد؛ فقط D2 را در بستر forward-fix ادامه می‌دهد. هیچ reverse schema در این mode انجام نمی‌شود مگر با eligibility جدا (بخش ۷.۲).

**Note — Ordering deviation from D2 (intentional, policy-compatible):** Mode A performs health/smoke verification before traffic resume, whereas the frozen D2 rollback/remediation ordering places health/smoke verification after resume. This difference is intentional: Mode A introduces a newly deployed forward-fix artifact while containment is active, so verification occurs before traffic exposure. D2 is not modified or reinterpreted by this note; this is forward-fix-specific ordering under containment.

### 3.5.2 Mode B — Forward-Fix بدون STOP (Normal Remediation)

اگر STOP criterion رخ نداده باشد و forward-fix یک remediation عادی باشد:

- این section به‌طور خودکار maintenance / write-freeze را اختراع نمی‌کند.
- Deployment تابع normal change-control و risk assessment خودش است.
- Health / smoke verification طبق بخش ۱۲.۲.
- اگر در جریان اجرا یک STOP criterion فعال شد → انتقال به Mode A.

نکته مرزی: Mode B یک مسیر سبک‌تر است، اما بدون عبور از approval boundaryهای مربوطه نیست. Deployment authorization همچنان لازم است.

---

## 3.6 Data Preflight (Contract — from Placeholder #4)

**Status of this contract:** governance-locked؛ executable artifact design-ready but absent.

### Input

- Migration target identifier (single، explicit)
- Declared conditions/invariants همان migration
- No credentials در CLI arguments — هیچ secret به‌عنوان argument
- Credentials از environment / standard Django config path (نه از CLI)

### Operation

- Read-only strictly enforced
- ممنوع: INSERT / UPDATE / DELETE
- ممنوع: repair · normalization · backfill
- ممنوع: migration execution
- ممنوع: هر side-effect روی data یا schema

### Output — machine-readable

حداقل شامل:

- `migration` — identifier
- `result` — `SAFE | UNSAFE` (فقط این دو مقدار)
- `checks` — فهرست checks اجراشده
- `violation_counts` — per check
- `errors` — evaluation errors (اگر وجود دارد)

### Fail-closed semantics

نتیجه نهایی نمی‌تواند SAFE باشد اگر:

- هر check اجباری اجرا نشده باشد
- Exception رخ داده باشد
- Timeout رخ داده باشد
- Output malformed باشد
- وضعیت نامعلوم (unknown) باشد
- یک required condition قابل evaluate نباشد

### Evidence linkage

Output قابل اتصال به:

- baseline / commit
- migration identifier
- execution timestamp
- change record

بدون secret یا PII غیرضروری.

### Exit semantics

- Deterministic برای automation
- SAFE از UNSAFE / evaluation-failure قابل تفکیک در process status
- عددهای دقیق exit-code → implementation می‌تواند در PR مربوطه تثبیت کند (spec فقط تفکیک‌پذیری را الزام می‌کند)

### Extensibility

- هر migration می‌تواند preflight-specific checks خودش را declare کند
- Generic check نباید به‌اشتباه safety همه migrationها را ادعا کند
- Safety ادعا فقط برای checks اجراشده‌ی همان migration معتبر است

### Automated vs Manual scope (per Placeholder #8)

- Automated scope: preconditions داده‌ای migration · violation counts · computable R-Data-Cond · declared invariants
- Manual scope: interpretation موارد غیر-deterministic · acceptance توسط Database Operator + Change Approver
- Guard: automation may not manufacture SAFE from judgment

### Acceptance Criterion — Empty Check-Set

Empty check-set نباید SAFE باشد مگر اینکه برای آن migration صراحتاً و در review ثبت شده باشد که هیچ data condition قابل‌بررسی وجود ندارد. این مانع «green by doing nothing» می‌شود.

### Testing requirement (minimum)

- SAFE fixture
- UNSAFE fixture
- Evaluation-error case
- Missing-required-check case
- Proof of no mutation (read-only enforcement)

### Review gate

- Implementation باید قبل از migration window در repo review شود
- اجرای همان artifact روی target environment باید SAFE تولید کند
- No self-approval در حوزه‌ای که خودش implement کرده (per DR baseline roles)

### Delivery

Implementation prerequisite: Canonical Data-Preflight Executable — design-ready (R2.9a)، artifact absent → Phase 3 NO-GO (بخش ۱۵.۴).

---

## 4. STOP Criteria

### 4.1 Frozen criteria (per ADR-016 — جایگزین‌ناپذیر)

- Execution budget exceeded
- Lock contention / deadlock
- Unexpected health probe state
- Database-level error
- Partial completion

Authority when 4.1 triggers: Incident Lead — unilateral STOP declaration (Section 4 Action بعدی، فوری و بدون consensus).

### 4.2 Supplemental criteria (پیشنهادی — نیازمند تأیید policy جداگانه)

- Data integrity check failure
- Application smoke test failure روی کد جدید
- Severe anomaly در application-level metrics

Authority when only 4.2 triggers (4.1 خالی): Change Approver decision در مشورت با Incident Lead. این یک STOP اجباری نیست — یک تصمیم governance است. Incident Lead می‌تواند برای safety به‌صورت unilateral توقف را اعلام کند، اما پیش‌فرض این حالت تصمیم Change Approver است. (رفع F2 — تفکیک صریح authority بین 4.1 و 4.2)

### Action after STOP (مطابق ترتیب D2)

1. Traffic Stop (۵.۱) — Incident Lead، unilateral
2. Write Freeze (۵.۲) — Incident Lead، unilateral
3. Notification chain
4. Evidence capture (۱۳)
5. Decision Entry Point (۶)

---

## 5. Traffic Stop and Write Freeze — Two Independent Controls

### 5.1 Traffic Stop / Maintenance (step 1)

- Entry authority: Incident Lead (unilateral)
- بلاک: incoming user requests، هر traffic که write ایجاد می‌کند

### 5.2 Write Freeze (step 2 — بعد از Traffic Stop)

- Entry authority: Incident Lead (unilateral)
- بلاک: application writes، backfill jobs، provisioning writes، scheduled tasks که write می‌کنند
- Not paused: backup protection (حذف‌شده از v0)

Exit از هر دو: Change Approver + Incident Lead، بعد از verification.

---

## 5.5 Role Assignment (from Placeholder #3)

Runbook operational roles تعریف می‌کند، نه اشخاص دائمی.

Mandatory per change window / rehearsal: Change Approver · Incident Lead · Database Operator · Application Verifier — به افراد مشخص assign و در change record ثبت شوند.

Guard: Multi-party / independent approvals با role co-assignment به یک فرد satisfy نمی‌شوند (Class A/B سه‌نقش، data-loss joint، schema reset joint، write-freeze exit).

Rotation: formal rotation referenceable when defined؛ تا آن زمان blocker نیست؛ نبود assignment صریح = NO-GO.

---

## 6. Decision Entry Point

- STOP declaration (4.1): Incident Lead — unilateral
- STOP decision (4.2 only): Change Approver در مشورت با Incident Lead
- Remediation path: Change Approver

---

## 7. Code / Schema Compatibility Assessment

### 7.1 Code rollback eligibility (per D2)

rollback code قبل از schema rollback فقط اگر old code با schema فعلی compatible باشد. در غیر این صورت → hold-state (۸.۱).

### 7.2 Reverse eligibility — Classification vocabulary

| کلاس | Reverse behavior |
|---|---|
| R-Schema | ✅ eligible |
| R-Data | ✅ eligible (مکمل) |
| R-Data-Cond | ✅ فقط اگر condition در لحظه satisfied باشد |
| F-Schema | ❌ reverse ممنوع مطلق |
| F-Data | ❌ reverse ممنوع مطلق |
| M-Schema | ⚠️ no automatic/routine؛ explicit state-based human decision + safety proof + approval |
| M-Data | ⚠️ no automatic/routine؛ explicit state-based human decision + safety proof + approval |

قواعد:

- R-* → eligibility عادی
- F-* → reverse ممنوع مطلق. هیچ approval آن را مجاز نمی‌کند.
- M-* → ابتدا state-based human decision، سپس safety proof، سپس approval. اگر ممکن نبود → forward-fix.

### 7.3 Forward-fix = default

اگر 7.2 نبود → forward-fix (بخش ۳.۵).

---

## 8. Reverse Migration Path (Conditional, Gated)

پیش‌شرط‌ها: eligibility (۷.۲) · Change Approver approval · D5 freshness satisfied · pre-reverse snapshot · Traffic Stop + Write Freeze فعال

مراحل (D2):

1. Stop traffic
2. Freeze writes
3. Rollback service layer (۷.۱) — اگر incompatible → hold-state (۸.۱)
4. Reverse migration — explicitly authorized only
5. Data restoration or reconciliation — conditional؛ approval صریح
6. Resume traffic بعد از compatibility
7. Verification

### 8.1 Hold-State

old code incompatible → do NOT roll back service code؛ traffic stopped + writes frozen باقی می‌مانند؛ Operator باید compatible code/schema target تعیین کند؛ هیچ schema reverse تا مستندسازی target + اثبات compatibility + approval صریح.

**DESTRUCTIVE — بدون authorization ممنوع. Reverse migration بخشی از restore rehearsal نیست.**

---

## 9. Restore Path

### 9.0 Preservation of Newer Valid Writes (Safety Prerequisite)

1. Database Operator: شناسایی writes بعد از backup (بازه، منابع)
2. Database Operator: طبقه‌بندی (recoverable · critical · discardable)
3. Database Operator: preparation + technical feasibility validation of preservation strategy — examples, not prescribed mechanisms (export، re-apply، external replay). Database Operator technical feasibility را تأیید می‌کند.
4. Change Approver: authorization of preservation strategy execution. Change Approver صرفاً اجرای strategy را authorize می‌کند؛ تهیه یا تأیید فنی آن وظیفه‌ی Database Operator است. (رفع F5 — همان الگوی reconciliation)
5. Stronger boundaries preserved: اگر strategy شامل intentional data loss، restore، cutover یا هر عملیات با boundary قوی‌تر باشد → آن approval مستقل همچنان لازم است:
   - intentional data loss → Change Approver + Incident Lead joint + external owner if applicable (#10)
   - restore → Class A/B boundaries
   - cutover → Class A boundary
6. [#10 resolved: Change Approver + Incident Lead joint — external owner if applicable]
7. Application Verifier: verifies نتیجه — verifier approver نیست.

بدون این گام، restore مجاز نیست.

### Class A — Isolated Recovery (پیش‌فرض)

- Restore به new/isolated database؛ `RESTORE_DATABASE_URL ≠ DATABASE_URL`
- Preservation (۹.۰) اعمال‌شده
- Cutover فقط بعد از validation
- Approval: Change Approver + Incident Lead + DB Operator

### Class B — In-Place Destructive Restore (Exceptional)

- Restore روی operational DB؛ فقط اگر Class A ممکن نباشد
- Preservation (۹.۰) — سخت‌گیرانه‌تر
- Approval مستقل سه‌نقش — independent
- Snapshot پیش از restore

### Class C — Infrastructure Rehearsal (isolated DR target)

- Target: [PLACEHOLDER #2 — still open، blocker]
- `STAGING_DATABASE_URL ≠ DR_RESTORE_DATABASE_URL`؛ PG 18؛ `confirm_restore=yes` gate؛ source/target guards غیرقابل bypass
- Schema reset: Placeholder #11 — Change Approver + DB Operator per-rehearsal؛ dependency on #2 (رفع F6 در Section 11)
- Dispatch: Change Approver per-dispatch (#9)
- Execution: Database Operator
- Verification: ۱۲.۱ + ۱۲.۲ + ۱۲.۳ manual acceptance
- D5 satisfied فقط با همه‌ی موارد فوق

---

## 10. Partial-Failure Reconciliation (D3-aligned)

تفکیک نقش‌ها:

1. Database Operator — prepares and technically validates: مقایسه actual schema/data state با `django_migrations`؛ تشخیص مرز partial application (completed / partial / not-yet-applied)؛ تهیه reconciliation plan فنی.
2. Change Approver — authorizes execution: انتخاب و تأیید اجرای reconciliation plan.
3. Database Operator — executes: طبق plan مصوب.
4. Application Verifier — verifies: طبق بخش ۱۲ (verification requirements)؛ verifier approver اجرای reconciliation نیست.
5. Incident Lead: containment را حفظ می‌کند؛ صرفاً Incident Lead بودن به معنی reconciliation authority نیست.
6. Guard — stronger boundaries preserved: اگر reconciliation plan شامل schema reverse، restore، cutover یا intentional data loss باشد → آن approval مستقل همچنان لازم است (schema reverse = ۷.۲ + بخش ۸؛ restore = Class A/B؛ cutover = Class A؛ data loss = #10).

ADR-016: `migrate <app> <last-good-state>` به‌تنهایی evidence کافی نیست.

---

## 11. Approval Boundaries (به‌روزشده با F4 و F6)

| Action | Approval | Role detail |
|---|---|---|
| Inspection، read-only verification | بدون approval | — |
| STOP (4.1 trigger) | Incident Lead — unilateral | Safety action |
| STOP (4.2 only trigger) | Change Approver در مشورت با Incident Lead | Governance decision |
| Traffic Stop entry | Incident Lead — unilateral | Containment |
| Write Freeze entry | Incident Lead — unilateral | Containment |
| Forward-fix code preparation | normal repository change-control | — |
| Forward-fix deployment (Mode A — containment) | explicit deployment authorization | — |
| Forward-fix deployment (Mode B — no STOP) | normal change-control + risk assessment؛ deployment authorization | — |
| Reconciliation plan execution | Change Approver authorizes | DB Operator prepares + technically validates؛ Application Verifier verifies (per §10) |
| Preservation strategy execution | Change Approver authorizes | DB Operator prepares + technically validates feasibility؛ Application Verifier verifies (per §9.0) |
| Reverse migration | Change Approver + eligibility (۷.۲) + [PLACEHOLDER — eligible cases only؛ F-* reverse prohibited per 7.2] | — |
| Isolated recovery + cutover (Class A) | Change Approver + Incident Lead + DB Operator | سه نقش — independent |
| In-place destructive restore (Class B) | Change Approver + Incident Lead + DB Operator | سه نقش — independent approval |
| Intentional data loss | Change Approver + Incident Lead joint + external owner if applicable | DB Operator = impact assessor (نه approver)؛ Application Verifier verifies (per §9.0)؛ [resolved #10] |
| Infrastructure rehearsal dispatch (Class C) | Change Approver per-dispatch | DB Operator executes؛ Application Verifier verifies (per §9 Class C)؛ [resolved #9] |
| Exit از Traffic Stop + Write Freeze | Change Approver + Incident Lead | — |
| Schema reset در Class C | Change Approver + DB Operator per-rehearsal — execution gated by #2 (DR target identity) | DB Operator re-verifies target + isolation قبل از authorization؛ Application Verifier verifies (per §9 Class C)؛ [resolved #11] |

[#3 resolved: role ≠ person؛ per-change assignment؛ multi-party boundaries با single-person satisfy نمی‌شوند]

---

## 12. Verification & Smoke Checks

### 12.1 Automated workflow verification (Class C)

Schema fingerprints · Table-count · Migrations · Content-types  
PASS لازم، ولی به‌تنهایی کافی نیست.

### 12.2 Full DR-baseline verification

`manage.py check --deploy` · App boots · `/health/` → 200 (DR baseline provenance) · `/healthz` → 200 (Render provenance، ثبت جدا) · Smoke: Home / Search / Library / Marketplace / Account · Representative-data integrity

### 12.3 Manual acceptance (per #8)

Interpretation of discrepancies · acceptance of result · record in evidence  
بدون این مرحله → Class C کامل نیست.

---

## 13. Evidence Capture

Timestamps (per `dr_staging_rehearsal.py`):

- `t0` = backup started
- `t1` = backup completed / restore point
- `t2` = restore completed
- `t3` = verification completed

Derived:

- restore duration = `t2 − t1`
- rehearsal RTO = `t3 − t0`

Logged: timestamps (t0–t3) · manual steps · approvals · fingerprint comparison · smoke results · RTO · deviations/decisions

Not logged: credential · secret · unnecessary PII

RPO: با یک rehearsal به‌تنهایی اثبات نمی‌شود

### 13.1 Evidence Store — Properties (Locked, from Placeholder #7)

Evidence Store = durable, access-controlled, change-linked repository خارج از ephemeral workflow/runtime storage.  
Exact implementation = organizational choice.

Minimum requirements:

| # | Requirement |
|---|---|
| 1 | Evidence به change/rehearsal ID و baseline/commit مربوطه قابل اتصال باشد |
| 2 | دسترسی write محدود؛ حذف/ویرایش evidence کنترل‌شده |
| 3 | Secrets، credentials و PII ذخیره نشوند |
| 4 | Artifacts لازم ثبت شوند (جدول 13.2) |
| 5 | GitHub Actions ephemeral logs/artifacts به‌تنهایی canonical نباشند — مگر retention/access requirements رسماً برای این purpose پذیرفته شوند |
| 6 | Canonical location پیش از اولین qualifying infrastructure rehearsal تعیین و در rehearsal record ثبت شود |

### 13.2 Required Evidence Artifacts

- Approvals (per-change، per-rehearsal)
- Timestamps t0–t3
- Automated results و fingerprints (schema، table-count، migrations، content-types)
- Full verification results (سطح ۱۲.۲)
- Manual acceptance (سطح ۱۲.۳)
- Deviations / decisions / interpretations

### 13.3 Fill-before-first-rehearsal field

**Field:** Exact Evidence Store URI / Location  
اگر location واقعی هنوز انتخاب نشده باشد → qualifying Class C rehearsal برای D5 = NO-GO. Evidence نباید بعداً معلوم شود کجا قرار است نگهداری شود.

---

## 14. Exit Criteria

- [ ] STOP criteria غیرفعال
- [ ] Data Preflight SAFE (per ۳.۶)
- [ ] Automated verification (۱۲.۱) PASS
- [ ] Full DR-baseline verification (۱۲.۲) PASS
- [ ] Manual acceptance (۱۲.۳) انجام‌شده
- [ ] Evidence Store URI/Location تعیین‌شده (precondition D5)
- [ ] Monitoring watch window بدون regression
- [ ] Evidence capture کامل
- [ ] Exit از Traffic Stop + Write Freeze approved
- [ ] Change Approver + Incident Lead sign-off

---

## 15. Placeholders، Prerequisites & Fields

### 15.1 Pre-approval placeholders — three-layer status صریح (F7)

| # | Placeholder | Status |
|---|---|---|
| 1 | STOP authority | ✅ RESOLVED (governance) — Incident Lead unilateral (4.1 only) |
| 2 | DR target identity | ❌ OPEN (provider-side) — blocker #11 + Class C rehearsal |
| 3 | Named roles / rotation | ✅ RESOLVED (governance) — role ≠ person؛ per-change assignment |
| 4 | Data-preflight canonical command | ✅ RESOLVED (governance contract) — implementation prerequisite OPEN (15.4) |
| 5 | Backup retention policy for Phase 2 | ❌ OPEN (provider-side) — may be plan-gated |
| 6 | Reconciliation approver role | ✅ RESOLVED (governance) — DB Operator + Change Approver |
| 7 | Evidence store location | ✅ RESOLVED (governance) — properties locked؛ URI/location field in 15.3 |
| 8 | Automated vs manual split | ✅ RESOLVED (governance) — evidence/deterministic vs judgment/acceptance |
| 9 | Rehearsal approver (Class C dispatch) | ✅ RESOLVED (governance) — Change Approver per-dispatch |
| 10 | data-loss approver / business owner | ✅ RESOLVED (governance) — CA + IL joint؛ external owner if applicable |
| 11 | Schema reset authorization | ✅ RESOLVED (governance) + execution gated by #2 — Change Approver + DB Operator per-rehearsal |

Progress: ۹ از ۱۱ closed at governance؛ #2 و #5 provider-side open؛ #4 implementation prerequisite open؛ #11 execution gated by #2.

### 15.2 Fill-at-change-time fields

Per-change execution budget · R-Data-Cond re-evaluation · Data-preflight execution + SAFE result · Change window announcement · Preservation strategy (per-incident) · Role assignment (چهار نقش پایه) · Rotation/on-call reference (اگر موجود)

### 15.3 Fill-before-first-rehearsal fields (F8 — متمایز از placeholders)

| Field | منبع |
|---|---|
| Exact Evidence Store URI/Location | value برای #7 (governance-resolved) |
| DR target identity | value برای #2 (open) |

### 15.4 Implementation prerequisites (جدا از placeholders)

| Prerequisite | وضعیت | Deadline |
|---|---|---|
| Canonical Data-Preflight Executable (#4) | design-ready؛ artifact absent → Phase 3 NO-GO | قبل از migration window مربوطه |

---

## 16. Non-Goals

- جایگزین approval process
- RPO/RTO commitment
- CI repo-contract rehearsal به‌جای infrastructure rehearsal
- اجرای destructive step بدون authorization
- Reverse migration بدون eligibility + approval
- دست‌زدن به PR #239

---

## 17. References

ADR-016 · `docs/disaster-recovery.md` · `.github/workflows/dr-staging-rehearsal.yml` · `scripts/dr_staging_rehearsal.py` · CI Backup Restore Rehearsal workflow

---

## Self-Review Checklist (v1.5)

- [x] F1 — Forward-Fix Path section موجود با دو mode (A: containment، B: no-STOP)
- [x] F2 — Section 4.2 authority تفکیک صریح از 4.1
- [x] F3 — Forward-fix ordering vs stop/freeze حل‌شده در Section 3.5.1
- [x] F4 — Section 11 reverse row: eligible cases only؛ F-* prohibited
- [x] F5 — Section 9.0 Step 4: DB Operator prep + Change Approver authorize؛ stronger boundaries preserved
- [x] F6 — Section 11 row #11: execution gated by #2
- [x] F7 — Section 15.1: three-layer status برچسب صریح
- [x] F8 — Section 15.1 vs 15.3: تمایز placeholder vs field value
- [x] Amendment v1.5 — Ordering deviation از D2 در Section 3.5.1 labeled
- [x] Frozen STOP criteria (4.1) بدون تغییر
- [x] D2 ordering بدون تغییر
- [x] Reverse eligibility vocabulary بدون تغییر
- [x] Preservation prerequisite بدون تغییر
- [x] Two-rehearsal distinction بدون تغییر
- [x] Timestamps t0–t3 بدون تغییر
- [x] Verification levels 12.1/12.2/12.3 بدون تغییر

---

## Current status

Rollback Runbook v1.5-R1 = **Policy-stable / Docs-ready**.

Explicitly open prerequisites remain:

- #2 DR target identity — provider-side؛ blocker #11 + Class C rehearsal
- #5 Backup retention policy — provider-side
- #4 Canonical Data-Preflight Executable — design-ready؛ artifact absent
- #11 schema reset execution — gated by #2

This document is policy-stable but not policy-frozen. It may be updated as new evidence resolves explicitly open prerequisites.
