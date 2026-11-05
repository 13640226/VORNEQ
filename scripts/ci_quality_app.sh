#!/bin/sh
# Quality verification, application side: runs inside the digest-pinned python
# image as an unprivileged user on an --internal network (no internet) and
# serves the app to the Playwright container under the alias "app".
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
python manage.py migrate --noinput
exec python manage.py runserver 0.0.0.0:8000 --noreload
