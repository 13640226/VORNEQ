#!/bin/sh
# Quality verification, browser side: runs inside the digest-pinned Playwright
# image as an unprivileged user on the same --internal network (no internet).
# node_modules were installed beforehand with `npm ci --ignore-scripts`.
set -eu
export HOME=/tmp

test "$(id -u)" != "0"
if command -v sudo >/dev/null 2>&1; then echo "sudo present" >&2; exit 1; fi
node -e '
const net = require("net");
const s = net.connect({ host: "registry.npmjs.org", port: 443 });
s.setTimeout(5000);
s.on("connect", () => { console.error("egress to registry.npmjs.org is open"); process.exit(1); });
s.on("error", () => { console.log("egress blocked: registry.npmjs.org unreachable"); process.exit(0); });
s.on("timeout", () => { console.log("egress blocked: registry.npmjs.org timed out"); process.exit(0); });
'

cp -r /src/quality /tmp/quality
cp -r /deps/node_modules /tmp/quality/node_modules
cd /tmp/quality

for i in $(seq 1 90); do
  if node -e 'fetch(process.env.QUALITY_BASE_URL + "/en/").then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))'; then
    break
  fi
  sleep 2
done
node -e 'fetch(process.env.QUALITY_BASE_URL + "/en/").then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))'

npm test
npm run verify
npm run lighthouse

mkdir -p /out
cp -r artifacts/quality/. /out/
