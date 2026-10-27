# VORNEQ — C02 evidence provenance and limitations

**Baseline:** `5446c9176e876d9a7a477b8203500a0e1d8334b1`  
**Git tree:** pinned commit tree read; `truncated=false`; 371 Python blobs in deterministic path order.

## Counts
| Item | Record |
|---|---|
| Historical batches | 001–038 (reported) |
| Python paths | 371 |
| Reported inspected unique paths | 371/371 |
| Independently reconciled historical batch corpus | INCOMPLETE |
| Recent SHA matching claim | 21/21 reported |
| Recent itemized entries available in publication preparation | 17 |
| Difference | 4 itemized records not reconstructed; do not assert complete 21-row provenance |

## Selected SHA attestations
| Path | Git Blob SHA | Source |
|---|---|---|
| `scripts/smoke_test.py` | `fd6ed473898505216823e19bdbced13cbdca07de` | Batch 038 |
| `scripts/db_target_guard.py` | `375c380411c19850c12cfc03c6620c7cbde751fa` | Batch 037 |
| `scripts/dr_staging_rehearsal.py` | `db12c56d440d4ab01d67ac895d77f49cb7300789` | Batch 037 |
| `marketplace/views.py` | `69eda40a9c5cb77e9342ea991ad30f30a058ce02` | Batch 037 |
| `marketplace/models.py` | `8e3334a81ff627c614e68257ddc40b26080f00c1` | Batch 036 |
| `marketplace/admin.py` | `420d815efad83bc8fd6d02301d63f84fa4eb025c` | Batch 035 |
| `library/views.py` | `c6de637ae185361163658bbea5aa8f4396d78949` | Batch 035 |

## Historical baseline distinction
A separate historical 371-file manifest is tied to `e3d32256dbe1e79664678ca77473f6135c0c9700` and tree `969c83c6e111a43cf5965338ecc180d0a27a64d3`. It is **not** interchangeable with the current pinned commit.

## Explicit limitations
- No full independent replay of all 38 batch attestations.
- No proof that every possible runtime callsite or indirect effect is safe.
- No runtime database identity verification; target UNKNOWN.
- No tests, SQL, database connections, secrets, deployments or changes to protected environments.
- The presence of these records in GitHub does not change authorization or security gates.

**Verdict:** `DOCUMENTARY_RECONCILIATION_PARTIAL / EVIDENCE_INCOMPLETE / SAFE_HOLD / NO_GO`.
