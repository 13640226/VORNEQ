# Chat V8 release recovery — 2026-11-27

The Render API deployment of 54f57fd58c2a86716756728cad232a274e98702e
on Staging (dep-dc4i8nec6qcc73dmhss0) was outside the owner-run
GitHub Deploy workflow. Render reported live and /health/ was healthy,
but Chat returned 404. No matching official Staging deployment record
existed. The follow-owner release policy correctly fails closed.

Recovery: reviewed new main commit, successful main CI and security,
fresh exact-SHA owner authorization on issue #448, then the owner
manually runs the official Deploy workflow for Staging. Do not replay
an already-live SHA, fabricate deployment evidence, change the
authorized SHA to bypass the proof, or disable release verification.

This corrective release also synchronizes the language-switch forms
with the selected conversation when history changes the URL without
reloading, and collapses history on narrow screens when starting a
new conversation. No provider, database schema, ledger or gate change.

After the official deployment, verify the expected live SHA, health,
official deployment evidence, anonymous Chat HTTP 401 and an authorized
user's actual Chat page. No paid call is needed for these checks.
Production remains out of scope.
