-- P0_VORNEQ_MARKETPLACE_SYNTHETIC_DATA_PROVENANCE_AND_SAFE_ISOLATION_V1_2
-- SOURCE_SHA=db54b0723798c2f8a3919eca4649865a0a10edf0
-- STATIC_PREPARATION_ONLY: No database execution has been authorized by this file.
-- PRODUCTION DATABASE ACCESS REQUIRES A SEPARATE OWNER C02 EXECUTION DECISION.
-- psql usage after separate authorization and target identity verification:
--   \set ON_ERROR_STOP on
--   \i P0_SYNTHETIC_PRODUCTS_READONLY_AUDIT_V1_2.sql
-- This SQL performs SELECT-only data access inside a READ ONLY transaction.
-- BEGIN/SET LOCAL/ROLLBACK control the session and do not modify data.

BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '15s';
SET LOCAL lock_timeout = '3s';

-- Q0: DB runtime identity and transaction mode (metadata; redact db_user if shared).
SELECT current_database() AS database,
       current_user AS db_user,
       current_setting('transaction_read_only') AS transaction_read_only,
       now() AS executed_at;

-- Q0G: fail-closed guard before reading product rows.
-- This SELECT causes an error on an unexpected database, user or read-only state.
-- psql must have ON_ERROR_STOP set to on; the transaction is read-only.
SELECT 1 / (
    (current_database() = 'vorneq_production_db'
     AND current_user = 'vorneq_production_db_user'
     AND current_setting('transaction_read_only') = 'on')::integer
) AS runtime_identity_guard;
-- Q1: Cross-classify candidate fixture products, expose marker mismatches.
WITH synth AS (
  SELECT p.id, p.status, p.is_published, p.created_at,
         (p.slug LIKE 'vorneq-benchmark-%' OR p.slug LIKE 'inspect-staging-smoke%') AS by_slug,
         (u.username IN ('vorneq-benchmark-seed', 'vorneq-inspect-smoke')) AS by_seller
  FROM marketplace_product p
  JOIN auth_user u ON u.id = p.seller_id
  WHERE p.slug LIKE 'vorneq-benchmark-%'
     OR p.slug LIKE 'inspect-staging-smoke%'
     OR u.username IN ('vorneq-benchmark-seed', 'vorneq-inspect-smoke')
)
SELECT by_slug, by_seller, status, is_published,
       COUNT(*) AS products,
       MIN(created_at) AS first_created,
       MAX(created_at) AS last_created
FROM synth
GROUP BY by_slug, by_seller, status, is_published
ORDER BY by_slug, by_seller, status, is_published;

-- Q2: Fixture timeline in UTC. 2026-10-26 is documentary comparison only.
WITH synth AS (
  SELECT p.created_at
  FROM marketplace_product p
  JOIN auth_user u ON u.id = p.seller_id
  WHERE p.slug LIKE 'vorneq-benchmark-%'
     OR p.slug LIKE 'inspect-staging-smoke%'
     OR u.username IN ('vorneq-benchmark-seed', 'vorneq-inspect-smoke')
)
SELECT CASE WHEN created_at < TIMESTAMPTZ '2026-10-26 00:00:00+00'
            THEN 'before_2026-10-26' ELSE 'on_or_after_2026-10-26' END AS period,
       (created_at AT TIME ZONE 'UTC')::date AS day_utc,
       COUNT(*) AS products
FROM synth
GROUP BY 1, 2
ORDER BY 2, 1;

-- Q3: Synthetic account flags; never output password content.
SELECT username, is_active, is_staff, is_superuser,
       date_joined, last_login,
       (password LIKE '!%') AS unusable_password
FROM auth_user
WHERE username IN ('vorneq-benchmark-seed', 'vorneq-inspect-smoke')
ORDER BY username;

-- Q4: Relationships/reviews/artifact bindings; include unexpired entitlements.
WITH synth AS (
  SELECT p.id
  FROM marketplace_product p
  JOIN auth_user u ON u.id = p.seller_id
  WHERE p.slug LIKE 'vorneq-benchmark-%'
     OR p.slug LIKE 'inspect-staging-smoke%'
     OR u.username IN ('vorneq-benchmark-seed', 'vorneq-inspect-smoke')
)
SELECT 'entitlements_total' AS check_name, COUNT(*) AS n
FROM core_entitlement e
WHERE e.product_id IN (SELECT id FROM synth)
UNION ALL
SELECT 'entitlements_active_flag_non_seed_users', COUNT(*)
FROM core_entitlement e
JOIN auth_user u ON u.id = e.user_id
WHERE e.product_id IN (SELECT id FROM synth)
  AND e.is_active
  AND u.username NOT IN ('vorneq-benchmark-seed', 'vorneq-inspect-smoke')
UNION ALL
SELECT 'entitlements_currently_valid_non_seed_users', COUNT(*)
FROM core_entitlement e
JOIN auth_user u ON u.id = e.user_id
WHERE e.product_id IN (SELECT id FROM synth)
  AND e.is_active
  AND (e.expires_at IS NULL OR e.expires_at > now())
  AND u.username NOT IN ('vorneq-benchmark-seed', 'vorneq-inspect-smoke')
UNION ALL
SELECT 'reviews_total', COUNT(*)
FROM marketplace_productreview r
WHERE r.product_id IN (SELECT id FROM synth)
UNION ALL
SELECT 'artifact_bindings', COUNT(*)
FROM core_artifactbinding b
JOIN django_content_type ct ON ct.id = b.content_type_id
WHERE ct.app_label = 'marketplace'
  AND ct.model = 'product'
  AND b.object_id IN (SELECT id::text FROM synth);

-- Q5: Non-synthetic catalog size by current markers; not immutable provenance.
SELECT COUNT(*) FILTER (WHERE p.status = 'approved' AND p.is_published) AS public_non_synthetic,
       COUNT(*) AS all_non_synthetic
FROM marketplace_product p
JOIN auth_user u ON u.id = p.seller_id
WHERE NOT (
  p.slug LIKE 'vorneq-benchmark-%'
  OR p.slug LIKE 'inspect-staging-smoke%'
  OR u.username IN ('vorneq-benchmark-seed', 'vorneq-inspect-smoke')
);

ROLLBACK;
