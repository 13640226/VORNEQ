#!/bin/sh
# CI-02: runs inside a network-less (or --internal) container as an unprivileged
# user. Dependencies come only from pre-downloaded, hash-verified wheels in /w.
set -eu
export HOME=/tmp

test "$(id -u)" != "0"
if command -v sudo >/dev/null 2>&1; then echo "sudo present" >&2; exit 1; fi

python - <<'EOF'
import socket, sys
for host in ("pypi.org", "github.com"):
    try:
        socket.create_connection((host, 443), timeout=5).close()
    except OSError:
        continue
    sys.exit(f"egress to {host} is open")
print("egress blocked: pypi.org, github.com unreachable")
EOF

cp -r /src /tmp/app
cd /tmp/app

python -m venv /tmp/venv
/tmp/venv/bin/pip install --no-index --find-links /w --require-hashes --only-binary=:all: -r /lock
PATH=/tmp/venv/bin:$PATH
export PATH

for po in $(find . -path ./node_modules -prune -o -name django.po -print); do
  pybabel compile -i "$po" -o "${po%.po}.mo"
done

python manage.py check

if [ -n "${DATABASE_URL:-}" ]; then
  python - <<'EOF'
import ipaddress, os, sys
from urllib.parse import urlparse
import psycopg2
url = os.environ["DATABASE_URL"]
host = urlparse(url).hostname
if host != "postgres":
    sys.exit(f"DATABASE_URL host {host!r} is not the job service alias 'postgres'")
with psycopg2.connect(url) as conn, conn.cursor() as cur:
    cur.execute("SELECT current_database(), current_user, host(inet_server_addr())")
    db, user, addr = cur.fetchone()
print(f"identity: {db}|{user}|{addr}")
if (db, user) != ("vorneq", "vorneq"):
    sys.exit(f"unexpected database identity {db}/{user}")
ip = ipaddress.ip_address(addr)
if not ip.is_private or ip.is_loopback:
    sys.exit(f"database address {addr} is not a private job-network address")
EOF
  python manage.py migrate --noinput
fi

python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput
python manage.py test
