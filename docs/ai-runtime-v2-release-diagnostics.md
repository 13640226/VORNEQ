# AI Runtime V2 release diagnostics

The existing runtime audit remains offline. For a hosted service, run the
following operator-only command in its Render shell with the **actual expected
SHA** (not a guessed pin):

```sh
python manage.py audit_ai_release --environment staging --expected-sha FULL_SHA
python manage.py audit_ai_release --environment staging --expected-sha FULL_SHA --verify-release
```

For Production use `--environment production`. The identity check rejects
the wrong service, environment, SHA or DEBUG mode before diagnosis.

The default mode never reads GitHub. The explicit verification option uses the
existing read-only deployment evidence API and the same evidence predicates
as the authorization gate. It makes a fresh observation, without changing the
authorization cache. The gate can therefore differ briefly due to cache TTL.

The report separates the Chat page from Global Chat and Staging Image Studio
from Production's independent read-only Studio preview. It includes fixed
reason codes for configuration and release evidence (including deployment
drift, missing token, invalid marker/status/workflow and unavailable evidence).
It never prints tokens, model configuration values, owner grants, allowlists,
API response bodies or exception messages.

`CONFIGURATION_READY` is not authorization: authenticated actor eligibility,
database account state, worker health and provider delivery are not verified.
`NOT_VERIFIED` means an offline observation could not establish release proof.
`BLOCKED` means at least one reported prerequisite did not pass.

Do not change a pin or disable follow-owner verification just to clear a
diagnostic. If Render is already live on a SHA without official GitHub
deployment evidence, use the reviewed new-commit recovery path in
`scripts/deploy_control.py` and the owner-run official Deploy workflow.
No diagnostic command performs a deployment, migration, paid request, ledger
reservation, storage access, or configuration mutation.
