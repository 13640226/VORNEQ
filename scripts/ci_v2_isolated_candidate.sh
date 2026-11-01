#!/usr/bin/env bash
# CI V2 isolated runtime candidate. NOT AUTHORIZED FOR EXECUTION.
# Requires an independently approved, pre-provisioned app image containing
# dependencies and a non-root account. No docker build/pull in this script.
set -Eeuo pipefail
umask 077

: "${CI_V2_APP_IMAGE_DIGEST:?Required approved sha256 image digest}"
: "${CI_V2_PG_IMAGE_DIGEST:?Required approved sha256 PostgreSQL image digest}"
: "${CI_V2_EXPECTED_SHA:?Required exact authorized source commit}"
: "${CI_V2_REVIEWED_RUN_ID:?Required independent runtime authorization identifier}"

[[ "$CI_V2_APP_IMAGE_DIGEST" =~ ^[a-zA-Z0-9./:_-]+@sha256:[0-9a-f]{64}$ ]] || exit 10
[[ "$CI_V2_PG_IMAGE_DIGEST" =~ ^[a-zA-Z0-9./:_-]+@sha256:[0-9a-f]{64}$ ]] || exit 11
[[ "$(git rev-parse HEAD)" == "$CI_V2_EXPECTED_SHA" ]] || exit 12
[[ "${GITHUB_ACTIONS:-}" == "true" ]] || exit 13
[[ "${GITHUB_EVENT_NAME:-}" == "workflow_dispatch" ]] || exit 14
[[ -z "${DATABASE_URL:-}" && -z "${REDIS_URL:-}" ]] || exit 15
[[ -z "${AWS_ACCESS_KEY_ID:-}" && -z "${RENDER_API_KEY:-}" ]] || exit 16

# This orchestrator requires Docker access. The untrusted application NEVER
# receives the Docker socket or host credentials.
command -v docker >/dev/null || exit 17
network="vorneq-ci2-${GITHUB_RUN_ID:-manual}-$$"
pg="vorneq-ci2-pg-$$"
cleanup() {
  docker rm -f "$pg" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker network create --internal "$network" >/dev/null
# No published ports, no production endpoints, disposable container.
docker run -d --name "$pg" --network "$network" --network-alias postgres \
  --read-only --tmpfs /var/run/postgresql:rw,noexec,nosuid \
  --tmpfs /var/lib/postgresql/data:rw,nosuid \
  --cap-drop ALL --security-opt no-new-privileges \
  -e POSTGRES_USER=ci_only -e POSTGRES_PASSWORD=ci_only -e POSTGRES_DB=ci_test \
  "$CI_V2_PG_IMAGE_DIGEST" >/dev/null
for i in $(seq 1 45); do
  if docker exec "$pg" pg_isready -U ci_only -d ci_test >/dev/null 2>&1; then break; fi
  sleep 1
done
docker exec "$pg" pg_isready -U ci_only -d ci_test >/dev/null
# Image MUST already contain Python, project requirements, and a nonroot user.
# Network is internal; application has no sudo, capabilities, host socket or secrets.
docker run --rm --network "$network" --user 65532:65532 \
  --cap-drop ALL --security-opt no-new-privileges --pids-limit 256 \
  --memory 2g --cpus 2 --read-only \
  --tmpfs /tmp:rw,nosuid,nodev --tmpfs /app/.cache:rw,nosuid,nodev \
  --mount "type=bind,src=$(pwd),dst=/src,readonly" \
  -e VORNEQ_ENV=development -e DJANGO_SECRET_KEY=ci-isolated-only \
  -e DJANGO_DEBUG=0 -e DJANGO_ALLOWED_HOSTS=localhost,testserver \
  -e DATABASE_URL=postgres://ci_only:ci_only@postgres:5432/ci_test \
  --workdir /src "$CI_V2_APP_IMAGE_DIGEST" \
  sh -c 'python -m django --version && python manage.py check && python manage.py migrate --noinput && python manage.py test'
