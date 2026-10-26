# Production PITR restore rehearsal

Purpose: prove that `vorneq-production-db` backups can actually be restored,
without touching the production database or the VORNEQ service.

Cadence: **monthly**, and after any change to the database plan, region,
PostgreSQL version or backup settings. Render PITR retention on the current
plan is 3 days, so a rehearsal only proves the recent window.

Every live step below needs its own explicit owner approval in chat
(`تأیید مالک: …`). Approval for one step does not carry over to the next.

## Fixed identifiers

| Resource | Render ID | Note |
| --- | --- | --- |
| VORNEQ web service | `srv-dadn07eq1p3s73eccau0` | runs the comparison from its Shell |
| Production DB `vorneq-production-db` | `dpg-dagru1h42hec73eqr960-a` | **never** restore, delete, restart or suspend |
| Rehearsal copy `vorneq-production-db-copy` | new ID each run | created and deleted by this runbook |

## Step 1 — Create the copy (owner approval required)

1. Render dashboard → `vorneq-production-db` → **Recovery** → Point-in-Time Recovery.
2. Pick a recent time, name the new database `vorneq-production-db-copy`,
   keep "copy settings" on, and press **Start Recovery**.
   PITR always restores into a **new** database; the source is not modified.
3. Wait until the copy shows **Available**. Record its `dpg-…` ID.
4. Check `GET /health/` on VORNEQ returns 200.

Stop if: the form targets the existing database instead of a new one, or the
new database name does not end in `-copy`.

## Step 2 — Read-only comparison (owner approval required)

Run in the **VORNEQ Shell** (Render dashboard → VORNEQ → Shell). The production
DB only accepts internal connections, so the comparison must run inside Render.

The owner copies the copy's **Internal Database URL** from its Connections tab
and pastes it at the hidden prompt. Never paste it into chat, a file or a commit.

```bash
read -s -p "COPY URL: " COPY_URL; echo; export COPY_URL; python manage.py shell -c "
import os, psycopg2
from django.db import connection
T=['django_migrations','auth_user','content_article','marketplace_product','library_libraryitem','media_mediaasset','evidence_provenancestep']
def q(cur):
    r={}
    for t in T:
        cur.execute('select count(*) from '+t); r[t]=cur.fetchone()[0]
    return r
a=q(connection.cursor())
c=psycopg2.connect(os.environ['COPY_URL']); c.set_session(readonly=True); b=q(c.cursor()); c.close()
for k in T: print(k, a[k], b[k], 'OK' if a[k]==b[k] else 'DIFF')
"; unset COPY_URL
```

Columns: table, production count, copy count, result. The copy session is
opened read-only; the production side runs `SELECT count(*)` only.

Pass: every row `OK`. A small `DIFF` on fast-changing tables can be explained
by writes after the chosen recovery time; a `DIFF` on `django_migrations` is a
failure and must be investigated before deleting the copy.

## Step 3 — Delete the copy (owner approval required)

1. Open the copy's page. Confirm the title is exactly `vorneq-production-db-copy`
   and the URL contains the copy's `dpg-…` ID, **not** `dpg-dagru1h42hec73eqr960-a`.
2. Settings → **Delete Database** → type the copy's name → confirm.
3. Check `GET /health/` returns 200 and the database list still shows
   `vorneq-production-db` as Available.

Stop if any page, URL or confirmation dialog names the production database.

## Rehearsal log

| Date (Europe/Berlin) | Copy ID | Result | Notes |
| --- | --- | --- | --- |
| 2026-10-26 | `dpg-dbfr467f3r2c73e84v3g-a` | **PASS** — 7/7 OK | First verified restore. Counts: django_migrations 85, auth_user 3, content_article 1000, marketplace_product 501, library_libraryitem 500, media_mediaasset 200, evidence_provenancestep 0. Copy created ~21:2x (approved), comparison 21:36 (run by owner; no separate approval sentence was written for this read-only step), copy deleted 21:40 (approved), `/health/` 200 at 21:41, database list confirmed by screenshot 21:41. Fresh export of current schema also taken 20:57. |
