# C02 — Corrected evidence provenance register
Pinned audit commit: `5446c9176e876d9a7a477b8203500a0e1d8334b1`
Status: PARTIAL_CORRECTIONS_PREPARED / EVIDENCE_INCOMPLETE

## Scope and claims
- Reported Python inventory: 371/371 across 38 reported batches. File-count coverage is **not** security clearance.
- The earlier statement of 21/21 recent SHA matches is a historical report, **not** a fully reconstructed 21-row manifest.
- Exactly **17 available path/SHA pairs** are itemized below: 10 from Batch 037, 1 from Batch 038, and 6 from Batch 036.
- Four remaining path/SHA pairs required to support a complete 21-entry table have **not** been recovered. They are not fabricated.
- The earlier published register contained 7 **selected examples**, not a full inventory.
- This documentation update does not independently re-fetch or verify all 17 blobs against the pinned tree.

## Historical SHA records (not newly verified in this correction)
| Batch | Index | Path | Reported Git Blob SHA | Evidence grade |
|---|---:|---|---|---|
| 037 | 361 | `marketplace/test_offline_admin_canonical_v2_golden_vectors.py` | `bac501a5a0ff93307923b4493b71462addf937a1` | HISTORICAL_BATCH_REPORTED |
| 037 | 362 | `marketplace/test_trust_context.py` | `8aa9e05e619cb3e8372b3dfb7e451dc3ceb21128` | HISTORICAL_BATCH_REPORTED |
| 037 | 363 | `marketplace/tests.py` | `537f0cfeb04090560f95d13da11e4d4e64dff161` | HISTORICAL_BATCH_REPORTED |
| 037 | 364 | `marketplace/urls.py` | `970a3a2326650f569da2a662e74f85f9d9377ad3` | HISTORICAL_BATCH_REPORTED |
| 037 | 365 | `marketplace/views.py` | `69eda40a9c5cb77e9342ea991ad30f30a058ce02` | HISTORICAL_BATCH_REPORTED |
| 037 | 366 | `marketplace/vorneq_app.py` | `72068e20128491a7599657e0d416c68fa9ebd730` | HISTORICAL_BATCH_REPORTED |
| 037 | 367 | `scripts/db_target_guard.py` | `375c380411c19850c12cfc03c6620c7cbde751fa` | HISTORICAL_BATCH_REPORTED |
| 037 | 368 | `scripts/dr_staging_rehearsal.py` | `db12c56d440d4ab01d67ac895d77f49cb7300789` | HISTORICAL_BATCH_REPORTED |
| 037 | 369 | `scripts/health_check.py` | `ba8504467024ca7b2f18777483f71345884fc5aa` | HISTORICAL_BATCH_REPORTED |
| 037 | 370 | `scripts/redesign_homepage.py` | `38d689329a062f82d9342e4343175934d12bb5a8` | HISTORICAL_BATCH_REPORTED |
| 038 | 371 | `scripts/smoke_test.py` | `fd6ed473898505216823e19bdbced13cbdca07de` | HISTORICAL_BATCH_REPORTED |
| 036 | not independently recovered | `marketplace/delivery.py` | `4b6e7404c9fd869db94f6727ebf13fd10fe80fd9` | HISTORICAL_BATCH_REPORTED |
| 036 | not independently recovered | `marketplace/forms.py` | `b3bfa8dc186dac302f6c4ca2d8fa404b5db0f207` | HISTORICAL_BATCH_REPORTED |
| 036 | not independently recovered | `marketplace/migrations/0001_initial.py` | `1140b533374c3945cfdadc0aa09c8d56117c9367` | HISTORICAL_BATCH_REPORTED |
| 036 | not independently recovered | `marketplace/migrations/0002_productreview_alter_product_options_and_more.py` | `d7aafd37e810e426fddf0c668387116c45f1215b` | HISTORICAL_BATCH_REPORTED |
| 036 | not independently recovered | `marketplace/models.py` | `8e3334a81ff627c614e68257ddc40b26080f00c1` | HISTORICAL_BATCH_REPORTED |
| 036 | not independently recovered | `marketplace/services.py` | `f167c93c4b990b0e5dd57043839dfd74d268fe5f` | HISTORICAL_BATCH_REPORTED |

## Reconciliation limits
- All 38 original batch manifests are not available for independent cross-check.
- Historical baseline `e3d32256dbe1e79664678ca77473f6135c0c9700` and tree `969c83c6e111a43cf5965338ecc180d0a27a64d3` are not interchangeable with the pinned audit commit.
- Production runtime database identity is UNKNOWN; destructive-operation safety is NOT_PROVEN.
- Independent security review remains PENDING.

## Evidence classes
E1 VERIFIED_SOURCE; E2 VERIFIED_BATCH_REPORT; E3 HISTORICAL_REPORTED; E4 RUNTIME_UNVERIFIED; E5 EVIDENCE_INCOMPLETE. The rows above are E3 in this correction, not newly established E1.

`STOP_340=ACTIVE; HARD_STOP=ACTIVE; C02=OPEN_CRITICAL; SC_07=OPEN_CRITICAL; R01=OPEN_CRITICAL; R02=OPEN_CRITICAL; DATABASE_GO=NO; MIGRATION_GO=NO; DEPLOY_GO=NO; PRODUCTION_RELEASE=BLOCKED; FINAL_STATE=SAFE_HOLD / NO_GO`
